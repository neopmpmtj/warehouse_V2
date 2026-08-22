import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import DataError, IntegrityError, transaction

from logging_utils import get_logger

from .models import (
    FamilyChangeLog,
    FamilyProduct,
    Item,
    ItemChangeLog,
    Supplier,
    SupplierChangeLog,
    SupplierItemPrice,
    SupplierItemPriceChangeLog,
    VatRate,
)

logger = get_logger("centcompras.products")

ITEM_UPDATABLE_FIELDS = (
    "family",
    "internal_code",
    "description",
    "unit_of_measure",
    "reorder_level",
    "vat_rate",
    "retail_price",
    "wholesale_price",
    "special_price",
)


INTERNAL_CODE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class DuplicateInternalCodeError(ValidationError):
    def __init__(self, internal_code):
        super().__init__(
            f'Internal code "{internal_code}" is already used by another item.',
            code="duplicate_internal_code",
        )


class InvalidInternalCodeError(ValidationError):
    def __init__(self):
        super().__init__(
            "Internal code may only contain letters, digits, dots, hyphens, and underscores.",
            code="invalid_internal_code",
        )


class DeactivateReasonRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "A reason is required to deactivate an item.",
            code="deactivate_reason_required",
        )


class ReactivateReasonRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "A reason is required to activate an item.",
            code="reactivate_reason_required",
        )


class FamilyNameRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "Family name is required.",
            code="family_name_required",
        )


class DuplicateFamilyNameError(ValidationError):
    def __init__(self, name):
        super().__init__(
            f'Family name "{name}" is already used.',
            code="duplicate_family_name",
        )


class InactiveFamilyError(ValidationError):
    def __init__(self, family=None):
        name = getattr(family, "name", None) or "family"
        super().__init__(
            f"Cannot assign items to inactive family '{name}'.",
            code="inactive_family",
        )


class SupplierNameRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "Supplier name is required.",
            code="supplier_name_required",
        )


class DuplicateSupplierNameError(ValidationError):
    def __init__(self, name):
        super().__init__(
            f'Supplier name "{name}" is already used.',
            code="duplicate_supplier_name",
        )


class InvalidSupplierEmailError(ValidationError):
    def __init__(self):
        super().__init__(
            "Enter a valid email address.",
            code="invalid_supplier_email",
        )


class DescriptionRequiredError(ValidationError):
    def __init__(self):
        super().__init__(
            "Description is required.",
            code="description_required",
        )


class InvalidSellingPriceError(ValidationError):
    def __init__(self, field_label="selling price"):
        super().__init__(
            f"{field_label} must be zero or greater.",
            code="invalid_selling_price",
        )


class InvalidReorderLevelError(ValidationError):
    def __init__(self, field_label="reorder level"):
        super().__init__(
            f"{field_label} must be zero or greater.",
            code="invalid_reorder_level",
        )


class InactiveSupplierError(ValidationError):
    def __init__(self, supplier=None):
        name = getattr(supplier, "name", None) or "supplier"
        super().__init__(
            f"Cannot use inactive supplier '{name}'.",
            code="inactive_supplier",
        )


class InactiveItemError(ValidationError):
    def __init__(self, item=None):
        label = (
            getattr(item, "internal_code", None)
            or getattr(item, "description", None)
            or "item"
        )
        super().__init__(
            f"Cannot use inactive item '{label}'.",
            code="inactive_item",
        )


def _serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, FamilyProduct):
        return {"id": value.pk, "name": value.name}
    if isinstance(value, VatRate):
        return {
            "id": value.pk,
            "code": value.code,
            "label": value.label,
            "rate": str(value.rate),
        }
    if isinstance(value, Supplier):
        return {"id": value.pk, "name": value.name}
    if isinstance(value, Item):
        return {
            "id": value.pk,
            "internal_code": value.internal_code,
            "description": value.description,
        }
    return value


def _normalize_internal_code(internal_code):
    return (internal_code or "").strip()


def validate_internal_code_format(internal_code):
    internal_code = _normalize_internal_code(internal_code)
    if not internal_code:
        return internal_code
    if INTERNAL_CODE_PATTERN.fullmatch(internal_code) is None:
        raise InvalidInternalCodeError()
    return internal_code


def validate_internal_code_available(internal_code, exclude_item_id=None):
    internal_code = validate_internal_code_format(internal_code)
    if not internal_code:
        return

    queryset = Item.objects.filter(internal_code__iexact=internal_code)
    if exclude_item_id is not None:
        queryset = queryset.exclude(pk=exclude_item_id)

    if queryset.exists():
        raise DuplicateInternalCodeError(internal_code)


def _resolve_family(family):
    if isinstance(family, FamilyProduct):
        return family
    return FamilyProduct.objects.get(pk=family)


def _ensure_family_active(family):
    if not FamilyProduct.objects.filter(pk=family.pk, is_active=True).exists():
        raise InactiveFamilyError(family)


def _ensure_supplier_active(supplier):
    if not Supplier.objects.filter(pk=supplier.pk, is_active=True).exists():
        raise InactiveSupplierError(supplier)


def _ensure_item_active(item):
    if not Item.objects.filter(pk=item.pk, is_active=True).exists():
        raise InactiveItemError(item)


def _validate_non_negative(value, field_label, error_cls):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise error_cls(field_label) from exc
    if not parsed.is_finite() or parsed < 0:
        raise error_cls(field_label)
    return parsed


def _resolve_vat_rate(vat_rate):
    if isinstance(vat_rate, VatRate):
        return vat_rate
    if isinstance(vat_rate, str):
        return VatRate.objects.get(code=vat_rate)
    return VatRate.objects.get(pk=vat_rate)


def _log_item_change(item, user, action, changes, reason=""):
    ItemChangeLog.objects.create(
        item=item,
        user=user,
        action=action,
        changes=changes,
        reason=reason.strip(),
    )


def _save_item(item, update_fields=None):
    try:
        with transaction.atomic():
            item.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
            if update_fields is None:
                item.save()
            else:
                item.save(update_fields=update_fields)
    except IntegrityError:
        validate_internal_code_available(
            item.internal_code,
            exclude_item_id=item.pk,
        )
        raise
    except DataError as exc:
        raise ValidationError(f"Invalid value: {exc}") from exc


@transaction.atomic
def create_item(
    user,
    family,
    description,
    unit_of_measure,
    vat_rate,
    internal_code="",
    reorder_level="0",
    retail_price="0",
    wholesale_price="0",
    special_price="0",
    reason="",
):
    internal_code = _normalize_internal_code(internal_code)
    validate_internal_code_available(internal_code)
    description = (description or "").strip()
    if not description:
        raise DescriptionRequiredError()
    family = _resolve_family(family)
    _ensure_family_active(family)
    vat_rate = _resolve_vat_rate(vat_rate)

    reorder_level = _validate_non_negative(
        reorder_level, "reorder_level", InvalidReorderLevelError
    )
    retail_price = _validate_non_negative(
        retail_price, "retail_price", InvalidSellingPriceError
    )
    wholesale_price = _validate_non_negative(
        wholesale_price, "wholesale_price", InvalidSellingPriceError
    )
    special_price = _validate_non_negative(
        special_price, "special_price", InvalidSellingPriceError
    )

    item = Item(
        family=family,
        internal_code=internal_code,
        description=description,
        unit_of_measure=unit_of_measure,
        reorder_level=reorder_level,
        retail_price=retail_price,
        wholesale_price=wholesale_price,
        special_price=special_price,
        vat_rate=vat_rate,
        is_active=False,
    )
    _save_item(item, update_fields=None)

    _log_item_change(
        item,
        user,
        ItemChangeLog.Action.CREATED,
        {
            "family": _serialize_value(item.family),
            "internal_code": _serialize_value(item.internal_code),
            "description": item.description,
            "unit_of_measure": item.unit_of_measure,
            "reorder_level": _serialize_value(item.reorder_level),
            "retail_price": _serialize_value(item.retail_price),
            "wholesale_price": _serialize_value(item.wholesale_price),
            "special_price": _serialize_value(item.special_price),
            "vat_rate": _serialize_value(item.vat_rate),
        },
        reason=reason,
    )

    logger.info(
        "Created item id=%s internal_code=%r description=%r family=%s user=%s",
        item.id,
        item.internal_code,
        item.description,
        item.family.name,
        getattr(user, "email", None),
    )

    return item


@transaction.atomic
def update_item(user, item, reason="", **fields):
    if not fields:
        return item

    unknown = set(fields) - set(ITEM_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    item = Item.objects.select_for_update().get(pk=item.pk)

    changes = {}
    pending_internal_code = None

    for field_name, new_value in fields.items():
        if field_name == "reorder_level":
            new_value = _validate_non_negative(
                new_value, "reorder_level", InvalidReorderLevelError
            )
        elif field_name in ("retail_price", "wholesale_price", "special_price"):
            new_value = _validate_non_negative(
                new_value, field_name, InvalidSellingPriceError
            )
        elif field_name == "internal_code":
            new_value = _normalize_internal_code(new_value)
            pending_internal_code = new_value
        elif field_name == "description":
            new_value = (new_value or "").strip()
            if not new_value:
                raise DescriptionRequiredError()
        elif field_name == "family":
            new_value = _resolve_family(new_value)
            _ensure_family_active(new_value)
        elif field_name == "vat_rate":
            new_value = _resolve_vat_rate(new_value)

        old_value = getattr(item, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": _serialize_value(old_value),
                "new": _serialize_value(new_value),
            }
            setattr(item, field_name, new_value)

    if not changes:
        return item

    if pending_internal_code is not None:
        validate_internal_code_available(
            pending_internal_code,
            exclude_item_id=item.pk,
        )

    _save_item(item, update_fields=[*changes.keys(), "updated_at"])
    _log_item_change(
        item,
        user,
        ItemChangeLog.Action.UPDATED,
        changes,
        reason=reason,
    )

    logger.info(
        "Updated item id=%s changes=%s user=%s",
        item.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )

    return item


@transaction.atomic
def deactivate_item(user, item, reason=""):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if not item.is_active:
        return item

    reason = (reason or "").strip()
    if not reason:
        raise DeactivateReasonRequiredError()

    item.is_active = False
    _save_item(item, update_fields=["is_active", "updated_at"])
    _log_item_change(
        item,
        user,
        ItemChangeLog.Action.DEACTIVATED,
        {},
        reason=reason,
    )

    logger.info(
        "Deactivated item id=%s user=%s",
        item.id,
        getattr(user, "email", None),
    )

    return item


@transaction.atomic
def reactivate_item(user, item, reason=""):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.is_active:
        return item

    reason = (reason or "").strip()
    if not reason:
        raise ReactivateReasonRequiredError()

    _ensure_family_active(item.family)

    item.is_active = True
    _save_item(item, update_fields=["is_active", "updated_at"])
    _log_item_change(
        item,
        user,
        ItemChangeLog.Action.REACTIVATED,
        {},
        reason=reason,
    )

    logger.info(
        "Reactivated item id=%s user=%s",
        item.id,
        getattr(user, "email", None),
    )

    return item


@transaction.atomic
def bulk_deactivate_items(user, items, reason=""):
    for item in items:
        deactivate_item(user, item, reason=reason)


@transaction.atomic
def bulk_reactivate_items(user, items, reason=""):
    for item in items:
        reactivate_item(user, item, reason=reason)


def get_items(active_only=True, family=None):
    queryset = Item.objects.select_related(
        "family", "vat_rate",
    ).order_by("id")
    if active_only:
        queryset = queryset.active()
    if family is not None:
        family = _resolve_family(family)
        queryset = queryset.filter(family=family)
    return queryset


def get_item_history(item):
    return item.change_logs.select_related("user").order_by("-created_at")


def get_vat_rates():
    return VatRate.objects.all().order_by("rate")


def _action_for_field_changes(changes, action_cls):
    if set(changes) == {"is_active"}:
        if changes["is_active"]["new"] is False:
            return action_cls.DEACTIVATED, {}
        return action_cls.REACTIVATED, {}
    return action_cls.UPDATED, changes


FAMILY_UPDATABLE_FIELDS = ("is_active",)


def _normalize_family_name(name):
    return (name or "").strip()


def validate_family_name_available(name, exclude_family_id=None):
    name = _normalize_family_name(name)
    if not name:
        raise FamilyNameRequiredError()

    queryset = FamilyProduct.objects.filter(name__iexact=name)
    if exclude_family_id is not None:
        queryset = queryset.exclude(pk=exclude_family_id)
    if queryset.exists():
        raise DuplicateFamilyNameError(name)
    return name


def _save_family(family, update_fields=None):
    try:
        with transaction.atomic():
            family.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
            if update_fields is None:
                family.save()
            else:
                family.save(update_fields=update_fields)
    except IntegrityError:
        validate_family_name_available(
            family.name,
            exclude_family_id=family.pk,
        )
        raise
    except DataError as exc:
        raise ValidationError(f"Invalid value: {exc}") from exc


def _log_family_change(family, user, action, changes, reason=""):
    FamilyChangeLog.objects.create(
        family=family,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


@transaction.atomic
def create_family(name, is_active=True, user=None):
    name = validate_family_name_available(name)
    family = FamilyProduct(
        name=name,
        is_active=is_active,
    )
    _save_family(family, update_fields=None)
    _log_family_change(
        family,
        user,
        FamilyChangeLog.Action.CREATED,
        {
            "name": family.name,
            "is_active": family.is_active,
        },
    )

    logger.info(
        "Created family id=%s name=%r user=%s",
        family.id,
        family.name,
        getattr(user, "email", None),
    )

    return family


@transaction.atomic
def update_family(family, user=None, **fields):
    if not fields:
        return family

    unknown = set(fields) - set(FAMILY_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    family = FamilyProduct.objects.select_for_update().get(pk=family.pk)

    changes = {}
    for field_name, new_value in fields.items():
        old_value = getattr(family, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": _serialize_value(old_value),
                "new": _serialize_value(new_value),
            }
            setattr(family, field_name, new_value)

    if not changes:
        return family

    _save_family(family, update_fields=[*changes.keys(), "updated_at"])
    action, logged_changes = _action_for_field_changes(
        changes,
        FamilyChangeLog.Action,
    )
    _log_family_change(family, user, action, logged_changes)

    logger.info(
        "Updated family id=%s action=%s fields=%s user=%s",
        family.id,
        action,
        list(changes.keys()),
        getattr(user, "email", None),
    )

    return family


def get_family_history(family):
    return family.change_logs.select_related("user").order_by("-created_at")


def get_families(active_only=True):
    queryset = FamilyProduct.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("name")


SUPPLIER_UPDATABLE_FIELDS = (
    "name",
    "contact_name",
    "email",
    "phone",
    "notes",
    "is_active",
)


def _normalize_supplier_name(name):
    return (name or "").strip()


def validate_supplier_name_available(name, exclude_supplier_id=None):
    name = _normalize_supplier_name(name)
    if not name:
        raise SupplierNameRequiredError()

    queryset = Supplier.objects.filter(name__iexact=name)
    if exclude_supplier_id is not None:
        queryset = queryset.exclude(pk=exclude_supplier_id)
    if queryset.exists():
        raise DuplicateSupplierNameError(name)
    return name


def _normalize_supplier_email(email):
    email = (email or "").strip()
    if not email:
        return ""
    try:
        validate_email(email)
    except ValidationError as exc:
        raise InvalidSupplierEmailError() from exc
    return email


def _save_supplier(supplier, update_fields=None):
    try:
        with transaction.atomic():
            supplier.full_clean(exclude=None, validate_unique=False, validate_constraints=False)
            if update_fields is None:
                supplier.save()
            else:
                supplier.save(update_fields=update_fields)
    except IntegrityError:
        validate_supplier_name_available(
            supplier.name,
            exclude_supplier_id=supplier.pk,
        )
        raise
    except DataError as exc:
        raise ValidationError(f"Invalid value: {exc}") from exc


def _log_supplier_change(supplier, user, action, changes, reason=""):
    SupplierChangeLog.objects.create(
        supplier=supplier,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


@transaction.atomic
def create_supplier(
    name,
    contact_name="",
    email="",
    phone="",
    notes="",
    is_active=True,
    user=None,
):
    name = validate_supplier_name_available(name)
    supplier = Supplier(
        name=name,
        contact_name=(contact_name or "").strip(),
        email=_normalize_supplier_email(email),
        phone=(phone or "").strip(),
        notes=(notes or "").strip(),
        is_active=bool(is_active),
    )
    _save_supplier(supplier, update_fields=None)
    _log_supplier_change(
        supplier,
        user,
        SupplierChangeLog.Action.CREATED,
        {
            "name": supplier.name,
            "contact_name": supplier.contact_name,
            "email": supplier.email,
            "phone": supplier.phone,
            "notes": supplier.notes,
            "is_active": supplier.is_active,
        },
    )

    logger.info(
        "Created supplier id=%s name=%r user=%s",
        supplier.id,
        supplier.name,
        getattr(user, "email", None),
    )

    return supplier


@transaction.atomic
def update_supplier(supplier, user=None, **fields):
    if not fields:
        return supplier

    unknown = set(fields) - set(SUPPLIER_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    supplier = Supplier.objects.select_for_update().get(pk=supplier.pk)

    changes = {}
    for field_name, new_value in fields.items():
        if field_name == "name":
            new_value = validate_supplier_name_available(
                new_value,
                exclude_supplier_id=supplier.pk,
            )
        elif field_name == "email":
            new_value = _normalize_supplier_email(new_value)
        elif field_name in ("contact_name", "phone", "notes"):
            new_value = (new_value or "").strip()
        old_value = getattr(supplier, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": _serialize_value(old_value),
                "new": _serialize_value(new_value),
            }
            setattr(supplier, field_name, new_value)

    if not changes:
        return supplier

    _save_supplier(supplier, update_fields=[*changes.keys(), "updated_at"])
    action, logged_changes = _action_for_field_changes(
        changes,
        SupplierChangeLog.Action,
    )
    _log_supplier_change(supplier, user, action, logged_changes)

    logger.info(
        "Updated supplier id=%s action=%s fields=%s user=%s",
        supplier.id,
        action,
        list(changes.keys()),
        getattr(user, "email", None),
    )

    return supplier


def get_supplier_history(supplier):
    return supplier.change_logs.select_related("user").order_by("-created_at")


def get_suppliers(active_only=True):
    queryset = Supplier.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("name")


SUPPLIER_ITEM_PRICE_UPDATABLE_FIELDS = ("cost_price", "primary")


class DuplicateSupplierItemPriceError(ValidationError):
    def __init__(self):
        super().__init__(
            "This supplier already has a price for this item.",
            code="duplicate_supplier_item_price",
        )


class DuplicatePrimarySupplierItemPriceError(ValidationError):
    def __init__(self):
        super().__init__(
            "This item already has a primary supplier price.",
            code="duplicate_primary_supplier_item_price",
        )


class InvalidCostPriceError(ValidationError):
    def __init__(self):
        super().__init__(
            "Cost price must be zero or greater.",
            code="invalid_cost_price",
        )


def _resolve_supplier(supplier):
    if isinstance(supplier, Supplier):
        return supplier
    return Supplier.objects.get(pk=supplier)


def _resolve_item(item):
    if isinstance(item, Item):
        return item
    return Item.objects.get(pk=item)


def _validate_cost_price(cost_price):
    try:
        value = Decimal(str(cost_price))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidCostPriceError() from exc
    if not value.is_finite() or value < 0:
        raise InvalidCostPriceError()
    return value


def _save_supplier_item_price(supplier_item_price, update_fields=None):
    try:
        with transaction.atomic():
            supplier_item_price.full_clean(
                exclude=None, validate_unique=False, validate_constraints=False
            )
            if update_fields is None:
                supplier_item_price.save()
            else:
                supplier_item_price.save(update_fields=update_fields)
    except IntegrityError as exc:
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        if "unique_primary_supplier_item_price" in str(cause):
            raise DuplicatePrimarySupplierItemPriceError() from exc
        raise DuplicateSupplierItemPriceError() from exc
    except DataError as exc:
        raise ValidationError(f"Invalid value: {exc}") from exc


def _log_supplier_item_price_change(
    supplier_item_price, user, action, changes, reason=""
):
    SupplierItemPriceChangeLog.objects.create(
        supplier_item_price=supplier_item_price,
        user=user,
        action=action,
        changes=changes,
        reason=(reason or "").strip(),
    )


def _clear_other_primaries(item, exclude_id=None, user=None):
    queryset = SupplierItemPrice.objects.select_for_update().filter(
        item=item, primary=True
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    for other in queryset:
        other.primary = False
        _save_supplier_item_price(other, update_fields=["primary", "updated_at"])
        _log_supplier_item_price_change(
            other,
            user,
            SupplierItemPriceChangeLog.Action.UPDATED,
            {
                "primary": {
                    "old": _serialize_value(True),
                    "new": _serialize_value(False),
                },
            },
        )


@transaction.atomic
def create_supplier_item_price(supplier, item, cost_price, primary=False, user=None):
    supplier = _resolve_supplier(supplier)
    item = _resolve_item(item)
    _ensure_supplier_active(supplier)
    _ensure_item_active(item)
    cost_price = _validate_cost_price(cost_price)
    primary = bool(primary)

    if primary:
        # Serialize primary mutations; clear others before insert (partial unique).
        item = Item.objects.select_for_update().get(pk=item.pk)
        _clear_other_primaries(item, exclude_id=None, user=user)

    supplier_item_price = SupplierItemPrice(
        supplier=supplier,
        item=item,
        cost_price=cost_price,
        primary=primary,
    )
    _save_supplier_item_price(supplier_item_price)

    _log_supplier_item_price_change(
        supplier_item_price,
        user,
        SupplierItemPriceChangeLog.Action.CREATED,
        {
            "supplier": _serialize_value(supplier),
            "item": _serialize_value(item),
            "cost_price": _serialize_value(cost_price),
            "primary": primary,
        },
    )

    logger.info(
        "Created supplier item price id=%s supplier=%s item=%r cost=%s primary=%s user=%s",
        supplier_item_price.id,
        supplier.name,
        item.internal_code or item.description,
        cost_price,
        primary,
        getattr(user, "email", None),
    )

    return supplier_item_price


@transaction.atomic
def update_supplier_item_price(supplier_item_price, user=None, **fields):
    if not fields:
        return supplier_item_price

    unknown = set(fields) - set(SUPPLIER_ITEM_PRICE_UPDATABLE_FIELDS)
    if unknown:
        raise ValueError(f"Cannot update fields: {', '.join(sorted(unknown))}")

    # Lock item before price when promoting to primary (same order as create).
    if "primary" in fields and bool(fields["primary"]):
        Item.objects.select_for_update().get(pk=supplier_item_price.item_id)

    supplier_item_price = SupplierItemPrice.objects.select_for_update().get(
        pk=supplier_item_price.pk
    )

    changes = {}
    for field_name, new_value in fields.items():
        if field_name == "cost_price":
            new_value = _validate_cost_price(new_value)
        elif field_name == "primary":
            new_value = bool(new_value)
        old_value = getattr(supplier_item_price, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": _serialize_value(old_value),
                "new": _serialize_value(new_value),
            }
            setattr(supplier_item_price, field_name, new_value)

    if not changes:
        return supplier_item_price

    becoming_primary = (
        "primary" in changes and changes["primary"]["new"] is True
    )
    if becoming_primary:
        _clear_other_primaries(
            supplier_item_price.item,
            exclude_id=supplier_item_price.pk,
            user=user,
        )

    _save_supplier_item_price(
        supplier_item_price, update_fields=[*changes.keys(), "updated_at"]
    )

    _log_supplier_item_price_change(
        supplier_item_price,
        user,
        SupplierItemPriceChangeLog.Action.UPDATED,
        changes,
    )

    logger.info(
        "Updated supplier item price id=%s changes=%s user=%s",
        supplier_item_price.id,
        list(changes.keys()),
        getattr(user, "email", None),
    )

    return supplier_item_price


def get_supplier_item_prices(item=None, supplier=None):
    queryset = SupplierItemPrice.objects.select_related("supplier", "item")
    if item is not None:
        queryset = queryset.filter(item=_resolve_item(item))
    if supplier is not None:
        queryset = queryset.filter(supplier=_resolve_supplier(supplier))
    return queryset.order_by("supplier__name", "item__description")


def get_supplier_item_price_history(supplier_item_price):
    return supplier_item_price.change_logs.select_related("user").order_by("-created_at")


def _buying_price_from_prices(prices):
    """O1: the primary supplier's cost, else the cheapest (None if no prices). Ignores deactivated suppliers."""
    active = [p for p in prices if p.supplier.is_active]
    primary = next((p for p in active if p.primary), None)
    if primary is not None:
        return primary.cost_price
    if active:
        return min(p.cost_price for p in active)
    return None


def get_item_buying_price(item):
    item = _resolve_item(item)
    prices = list(SupplierItemPrice.objects.filter(item=item).select_related("supplier"))
    return _buying_price_from_prices(prices)


def get_catalog(active_only=True, family=None):
    """Read-only manager-catalog join: item + family + prices + cached stock."""
    queryset = (
        Item.objects.select_related("family", "vat_rate")
        .prefetch_related("supplier_prices__supplier")
        .order_by("id")
    )
    if active_only:
        queryset = queryset.active().filter(family__is_active=True)
    if family is not None:
        queryset = queryset.filter(family=_resolve_family(family))
    return queryset


def catalog_buying_price(item):
    """O1 buying price from already-prefetched supplier prices (no extra query)."""
    return _buying_price_from_prices(list(item.supplier_prices.all()))


def catalog_below_reorder(item):
    """True when the item has a reorder level and stock is at/below it."""
    return item.reorder_level > 0 and item.quantity <= item.reorder_level
