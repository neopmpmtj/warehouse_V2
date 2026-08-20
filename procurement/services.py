from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from logging_utils import get_logger

from products.models import Item, Supplier, SupplierItemPrice

from .models import PurchaseOrder, PurchaseOrderChangeLog, PurchaseOrderLine

logger = get_logger("centcompras.procurement")

PO_UPDATABLE_FIELDS = ("supplier_ref", "notes")
LINE_UPDATABLE_FIELDS = (
    "quantity",
    "unit_cost",
    "discount_commercial",
    "discount_financial",
    "rappel",
)

STATUS_TRANSITIONS = {
    PurchaseOrder.Status.DRAFT: {PurchaseOrder.Status.SUBMITTED},
    PurchaseOrder.Status.SUBMITTED: {
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.REJECTED,
    },
    PurchaseOrder.Status.APPROVED: {PurchaseOrder.Status.RECEIVED},
    PurchaseOrder.Status.RECEIVED: {PurchaseOrder.Status.CLOSED},
}


class InvalidStatusTransitionError(ValidationError):
    def __init__(self, from_status, to_status):
        super().__init__(
            f"Cannot move a purchase order from '{from_status}' to '{to_status}'.",
            code="invalid_status_transition",
        )


class PurchaseOrderNotDraftError(ValidationError):
    def __init__(self):
        super().__init__(
            "Purchase order lines can only be changed while the order is a draft.",
            code="purchase_order_not_draft",
        )


class SupplierPriceMissingError(ValidationError):
    def __init__(self):
        super().__init__(
            "This supplier does not have a price for this item.",
            code="supplier_price_missing",
        )


def _resolve_supplier(supplier):
    if isinstance(supplier, Supplier):
        return supplier
    return Supplier.objects.get(pk=supplier)


def _resolve_item(item):
    if isinstance(item, Item):
        return item
    return Item.objects.get(pk=item)


def _resolve_po(po):
    if isinstance(po, PurchaseOrder):
        return po
    return PurchaseOrder.objects.get(pk=po)


def _log(po, user, action, changes, reason=""):
    PurchaseOrderChangeLog.objects.create(
        purchase_order=po,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


def _ensure_draft(po):
    if po.status != PurchaseOrder.Status.DRAFT:
        raise PurchaseOrderNotDraftError()


def _validate_quantity(quantity):
    value = Decimal(str(quantity))
    if value <= 0:
        raise ValidationError("quantity must be greater than zero.", code="invalid_quantity")
    return value


def _validate_unit_cost(unit_cost):
    value = Decimal(str(unit_cost))
    if value < 0:
        raise ValidationError("unit_cost must be zero or greater.", code="invalid_unit_cost")
    return value


def _validate_discount(value, field_name):
    amount = Decimal(str(value))
    if amount < 0 or amount > 100:
        raise ValidationError(
            f"{field_name} must be between 0 and 100.",
            code="invalid_discount",
        )
    return amount


def _validate_total_discount(commercial, financial, rappel):
    total = (
        Decimal(str(commercial))
        + Decimal(str(financial))
        + Decimal(str(rappel))
    )
    if total > 100:
        raise ValidationError(
            "Commercial, financial and rappel discounts cannot exceed 100% combined.",
            code="invalid_total_discount",
        )


def suggested_supplier(item):
    """Return the item's preferred (primary) supplier, else its cheapest."""
    item = _resolve_item(item)
    price = (
        SupplierItemPrice.objects.filter(item=item)
        .select_related("supplier")
        .order_by("-primary", "cost_price")
        .first()
    )
    return price.supplier if price else None


@transaction.atomic
def create_purchase_order(supplier, user, supplier_ref="", notes=""):
    supplier = _resolve_supplier(supplier)
    po = PurchaseOrder(
        supplier=supplier,
        created_by=user,
        supplier_ref=(supplier_ref or "").strip(),
        notes=(notes or "").strip(),
        status=PurchaseOrder.Status.DRAFT,
    )
    po.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
    po.save()

    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.CREATED,
        {
            "supplier": {"id": supplier.id, "name": supplier.name},
            "supplier_ref": po.supplier_ref,
            "notes": po.notes,
            "status": po.status,
        },
    )

    logger.info(
        "Created purchase order id=%s supplier=%s user=%s",
        po.id,
        supplier.name,
        getattr(user, "email", None),
    )
    return po


@transaction.atomic
def add_line(
    po,
    item,
    quantity,
    unit_cost=None,
    user=None,
    discount_commercial="0",
    discount_financial="0",
    rappel="0",
):
    po = _resolve_po(po)
    _ensure_draft(po)
    item = _resolve_item(item)
    quantity = _validate_quantity(quantity)

    supplier_price = SupplierItemPrice.objects.filter(
        supplier=po.supplier, item=item
    ).first()
    if supplier_price is None:
        raise SupplierPriceMissingError()

    if unit_cost is None:
        unit_cost = supplier_price.cost_price
    unit_cost = _validate_unit_cost(unit_cost)
    discount_commercial = _validate_discount(discount_commercial, "discount_commercial")
    discount_financial = _validate_discount(discount_financial, "discount_financial")
    rappel = _validate_discount(rappel, "rappel")
    _validate_total_discount(discount_commercial, discount_financial, rappel)

    line = PurchaseOrderLine(
        purchase_order=po,
        item=item,
        description=item.description,
        internal_code=item.internal_code,
        unit_of_measure=item.unit_of_measure,
        quantity=quantity,
        unit_cost=unit_cost,
        discount_commercial=discount_commercial,
        discount_financial=discount_financial,
        rappel=rappel,
        vat_rate=item.vat_rate.rate,
    )
    line.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
    line.save()

    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.LINE_ADDED,
        {
            "line_id": line.id,
            "item_id": item.id,
            "description": item.description,
            "internal_code": item.internal_code,
            "quantity": str(quantity),
            "unit_cost": str(unit_cost),
        },
    )

    logger.info(
        "Added line id=%s to purchase order id=%s item=%s user=%s",
        line.id,
        po.id,
        item.internal_code or item.description,
        getattr(user, "email", None),
    )
    return line


@transaction.atomic
def update_line(line, user=None, **fields):
    if not fields:
        return line

    unknown = set(fields) - set(LINE_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    line = PurchaseOrderLine.objects.select_for_update().get(pk=line.pk)
    _ensure_draft(line.purchase_order)

    changes = {}
    for field_name, new_value in fields.items():
        if field_name == "quantity":
            new_value = _validate_quantity(new_value)
        elif field_name == "unit_cost":
            new_value = _validate_unit_cost(new_value)
        elif field_name in ("discount_commercial", "discount_financial", "rappel"):
            new_value = _validate_discount(new_value, field_name)

        old_value = getattr(line, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": str(old_value), "new": str(new_value)}
            setattr(line, field_name, new_value)

    if not changes:
        return line

    _validate_total_discount(
        line.discount_commercial,
        line.discount_financial,
        line.rappel,
    )
    line.save(update_fields=[*changes.keys(), "updated_at"])
    _log(
        line.purchase_order,
        user,
        PurchaseOrderChangeLog.Action.LINE_UPDATED,
        {"line_id": line.id, **changes},
    )

    logger.info(
        "Updated line id=%s changes=%s user=%s",
        line.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )
    return line


@transaction.atomic
def remove_line(line, user=None):
    line = PurchaseOrderLine.objects.select_for_update().get(pk=line.pk)
    _ensure_draft(line.purchase_order)
    po = line.purchase_order
    line_id = line.id

    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.LINE_REMOVED,
        {
            "line_id": line_id,
            "item_id": line.item_id,
            "description": line.description,
            "quantity": str(line.quantity),
        },
    )
    line.delete()

    logger.info(
        "Removed line id=%s from purchase order id=%s user=%s",
        line_id,
        po.id,
        getattr(user, "email", None),
    )


def _transition(po, to_status):
    from_status = po.status
    if to_status not in STATUS_TRANSITIONS.get(from_status, set()):
        raise InvalidStatusTransitionError(from_status, to_status)


@transaction.atomic
def update_purchase_order(po, user=None, **fields):
    if not fields:
        return po

    unknown = set(fields) - set(PO_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    _ensure_draft(po)

    changes = {}
    for field_name, new_value in fields.items():
        if field_name in ("supplier_ref", "notes"):
            new_value = (new_value or "").strip()
        old_value = getattr(po, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": str(old_value),
                "new": str(new_value),
            }
            setattr(po, field_name, new_value)

    if not changes:
        return po

    po.save(update_fields=[*changes.keys(), "updated_at"])
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.FIELD_UPDATED,
        changes,
    )

    logger.info(
        "Updated purchase order id=%s changes=%s user=%s",
        po.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )
    return po


@transaction.atomic
def submit(po, user=None):
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if not po.lines.exists():
        raise ValidationError(
            "Cannot submit a purchase order without lines.",
            code="empty_purchase_order",
        )
    _transition(po, PurchaseOrder.Status.SUBMITTED)
    po.status = PurchaseOrder.Status.SUBMITTED
    po.save(update_fields=["status", "updated_at"])
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": PurchaseOrder.Status.DRAFT, "new": PurchaseOrder.Status.SUBMITTED}},
    )
    logger.info("Submitted purchase order id=%s user=%s", po.id, getattr(user, "email", None))
    return po


@transaction.atomic
def approve(po, user=None):
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    _transition(po, PurchaseOrder.Status.APPROVED)
    net, vat, gross = po.totals()
    po.status = PurchaseOrder.Status.APPROVED
    po.approved_by = user
    po.approved_at = timezone.now()
    po.approved_net = net
    po.approved_vat = vat
    po.approved_gross = gross
    po.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "approved_net",
            "approved_vat",
            "approved_gross",
            "updated_at",
        ]
    )
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.STATUS_CHANGED,
        {
            "status": {"old": PurchaseOrder.Status.SUBMITTED, "new": PurchaseOrder.Status.APPROVED},
            "approved_net": str(net),
            "approved_vat": str(vat),
            "approved_gross": str(gross),
        },
    )
    notify_supplier_on_approval(po)
    logger.info("Approved purchase order id=%s user=%s", po.id, getattr(user, "email", None))
    return po


@transaction.atomic
def reject(po, user=None):
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    _transition(po, PurchaseOrder.Status.REJECTED)
    po.status = PurchaseOrder.Status.REJECTED
    po.save(update_fields=["status", "updated_at"])
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": PurchaseOrder.Status.SUBMITTED, "new": PurchaseOrder.Status.REJECTED}},
    )
    logger.info("Rejected purchase order id=%s user=%s", po.id, getattr(user, "email", None))
    return po


@transaction.atomic
def receive(po, user=None):
    """Transition approved -> received. Stock is written in Phase 3 (goods receipt)."""
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    _transition(po, PurchaseOrder.Status.RECEIVED)
    po.status = PurchaseOrder.Status.RECEIVED
    po.save(update_fields=["status", "updated_at"])
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": PurchaseOrder.Status.APPROVED, "new": PurchaseOrder.Status.RECEIVED}},
    )
    logger.info("Received purchase order id=%s user=%s", po.id, getattr(user, "email", None))
    return po


@transaction.atomic
def close(po, user=None):
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    _transition(po, PurchaseOrder.Status.CLOSED)
    po.status = PurchaseOrder.Status.CLOSED
    po.save(update_fields=["status", "updated_at"])
    _log(
        po,
        user,
        PurchaseOrderChangeLog.Action.STATUS_CHANGED,
        {"status": {"old": PurchaseOrder.Status.RECEIVED, "new": PurchaseOrder.Status.CLOSED}},
    )
    logger.info("Closed purchase order id=%s user=%s", po.id, getattr(user, "email", None))
    return po


def notify_supplier_on_approval(po):
    """Stub for Phase 6 (email automation). Logs intent only."""
    logger.info(
        "Would notify supplier %s about approval of PO #%s (stub)",
        po.supplier.name,
        po.id,
    )


def get_purchase_orders(status=None):
    queryset = PurchaseOrder.objects.select_related("supplier", "created_by").prefetch_related("lines")
    if status is not None:
        queryset = queryset.filter(status=status)
    return queryset


def get_purchase_order_history(po):
    return po.change_logs.select_related("user").order_by("-created_at")
