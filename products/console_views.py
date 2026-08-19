import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.groups import (
    ADD_FAMILY,
    ADD_ITEM,
    ADD_SUPPLIER,
    CHANGE_FAMILY,
    CHANGE_ITEM,
    CHANGE_SUPPLIER,
)
from logging_utils import get_logger

from .models import FamilyProduct, Item, Supplier
from .permissions import catalog_permissions, catalog_required, deny_unless
from .services import (
    DeactivateReasonRequiredError,
    DuplicateFamilyNameError,
    DuplicateInternalCodeError,
    DuplicateSupplierNameError,
    FamilyNameRequiredError,
    InvalidSupplierEmailError,
    ReactivateReasonRequiredError,
    SupplierNameRequiredError,
    create_family,
    create_item,
    create_supplier,
    deactivate_item,
    get_families,
    get_family_history,
    get_item_history,
    get_items,
    get_supplier_history,
    get_suppliers,
    get_vat_rates,
    reactivate_item,
    update_family,
    update_item,
    update_supplier,
)

logger = get_logger("centcompras.products")

VALID_UNITS = {choice[0] for choice in Item.UnitOfMeasure.choices}


def _json_error(message, status=400, code=None):
    payload = {"error": message}
    if code:
        payload["code"] = code
    return JsonResponse(payload, status=status)


def _parse_json(request):
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        raise ValidationError("Request body must be valid JSON.")
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def _decimal_string(value):
    return str(value)


def _serialize_vat_rate(vat_rate):
    return {
        "id": vat_rate.id,
        "code": vat_rate.code,
        "label": vat_rate.label,
        "rate": _decimal_string(vat_rate.rate),
    }


def _serialize_family(family):
    payload = {
        "id": family.id,
        "name": family.name,
        "is_active": family.is_active,
    }
    item_count = getattr(family, "item_count", None)
    if item_count is not None:
        payload["item_count"] = item_count
    return payload


def _serialize_item(item):
    return {
        "id": item.id,
        "internal_code": item.internal_code,
        "description": item.description,
        "unit_of_measure": item.unit_of_measure,
        "reorder_level": _decimal_string(item.reorder_level),
        "is_active": item.is_active,
        "family": _serialize_family(item.family),
        "vat_rate": _serialize_vat_rate(item.vat_rate),
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _serialize_history_entry(entry):
    user_email = ""
    if entry.user_id:
        user_email = entry.user.email
    return {
        "id": entry.id,
        "action": entry.action,
        "reason": entry.reason,
        "changes": entry.changes,
        "user_email": user_email,
        "created_at": entry.created_at.isoformat(),
    }


def _unit_choices():
    return [
        {"value": value, "label": label}
        for value, label in Item.UnitOfMeasure.choices
    ]


def _console_payload(request):
    items = get_items(active_only=False)
    return {
        "items": [_serialize_item(item) for item in items],
        "families": [
            _serialize_family(family)
            for family in _families_with_counts()
        ],
        "units": _unit_choices(),
        "vat_rates": [_serialize_vat_rate(vr) for vr in get_vat_rates()],
        "permissions": catalog_permissions(request.user),
    }


def _parse_decimal(payload, field_name, required=True):
    if field_name not in payload:
        if required:
            raise ValidationError(f"{field_name} is required.")
        return None
    try:
        return Decimal(str(payload[field_name]))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number.") from exc


def _parse_unit(payload, required=True):
    if "unit_of_measure" not in payload:
        if required:
            raise ValidationError("unit_of_measure is required.")
        return None
    unit = str(payload["unit_of_measure"])
    if unit not in VALID_UNITS:
        raise ValidationError("unit_of_measure is not a valid choice.")
    return unit


def _serialize_supplier(supplier):
    return {
        "id": supplier.id,
        "name": supplier.name,
        "contact_name": supplier.contact_name,
        "email": supplier.email,
        "phone": supplier.phone,
        "notes": supplier.notes,
        "is_active": supplier.is_active,
    }


def _families_with_counts():
    return get_families(active_only=False).annotate(
        item_count=Count("items"),
    )


def _get_family(family_id):
    return _families_with_counts().get(pk=family_id)


def _family_response(family):
    family = _get_family(family.pk)
    return JsonResponse({"family": _serialize_family(family)})


def _get_item(item_id):
    return Item.objects.select_related("family", "vat_rate").get(pk=item_id)


def _item_response(item):
    item = _get_item(item.pk)
    return JsonResponse({"item": _serialize_item(item)})


@catalog_required
@require_GET
def item_console(request):
    return render(request, "products/item_console.html")


@catalog_required
@require_http_methods(["GET", "POST"])
def manage_item_list(request):
    if request.method == "GET":
        return JsonResponse(_console_payload(request))

    denied = deny_unless(request, ADD_ITEM)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        description = str(payload.get("description", "")).strip()
        if not description:
            raise ValidationError("description is required.")
        family_id = payload.get("family_id")
        if family_id is None:
            raise ValidationError("family_id is required.")
        vat_rate_id = payload.get("vat_rate_id")
        if vat_rate_id is None:
            raise ValidationError("vat_rate_id is required.")
        item = create_item(
            request.user,
            family=int(family_id),
            description=description,
            unit_of_measure=_parse_unit(payload),
            vat_rate=int(vat_rate_id),
            internal_code=str(payload.get("internal_code", "")),
            reorder_level=_parse_decimal(payload, "reorder_level")
            if "reorder_level" in payload
            else "0",
            reason=str(payload.get("reason", "")),
        )
    except DuplicateInternalCodeError as exc:
        return _json_error(exc.messages[0])
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) and getattr(exc, "messages", None) else str(exc)
        return _json_error(message)

    logger.info("Console created item id=%s user=%s", item.id, request.user.email)
    return _item_response(item)


@catalog_required
@require_http_methods(["GET", "PATCH"])
def manage_item_detail(request, item_id):
    try:
        item = _get_item(item_id)
    except Item.DoesNotExist:
        return _json_error("Item not found.", status=404)

    if request.method == "GET":
        return JsonResponse({"item": _serialize_item(item)})

    denied = deny_unless(request, CHANGE_ITEM)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        fields = {}
        if "description" in payload:
            description = str(payload["description"]).strip()
            if not description:
                raise ValidationError("description is required.")
            fields["description"] = description
        if "internal_code" in payload:
            fields["internal_code"] = str(payload["internal_code"])
        if "family_id" in payload:
            fields["family"] = int(payload["family_id"])
        if "unit_of_measure" in payload:
            fields["unit_of_measure"] = _parse_unit(payload)
        if "reorder_level" in payload:
            fields["reorder_level"] = _parse_decimal(payload, "reorder_level")
        if "vat_rate_id" in payload:
            fields["vat_rate"] = int(payload["vat_rate_id"])

        item = update_item(
            request.user,
            item,
            reason=str(payload.get("reason", "")),
            **fields,
        )
    except DuplicateInternalCodeError as exc:
        return _json_error(exc.messages[0])
    except (ValidationError, ObjectDoesNotExist, ValueError, TypeError) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) and getattr(exc, "messages", None) else str(exc)
        return _json_error(message)

    logger.info("Console updated item id=%s user=%s", item.id, request.user.email)
    return _item_response(item)


@catalog_required
@require_POST
def manage_item_deactivate(request, item_id):
    denied = deny_unless(request, CHANGE_ITEM)
    if denied:
        return denied
    return _lifecycle(request, item_id, deactivate_item)


@catalog_required
@require_POST
def manage_item_reactivate(request, item_id):
    denied = deny_unless(request, CHANGE_ITEM)
    if denied:
        return denied
    return _lifecycle(request, item_id, reactivate_item)


def _lifecycle(request, item_id, action):
    try:
        item = _get_item(item_id)
        payload = _parse_json(request) if request.body else {}
        item = action(
            request.user,
            item,
            reason=str(payload.get("reason", "")),
        )
    except json.JSONDecodeError:
        return _json_error("Request body must be valid JSON.")
    except Item.DoesNotExist:
        return _json_error("Item not found.", status=404)
    except (DeactivateReasonRequiredError, ReactivateReasonRequiredError) as exc:
        return _json_error(exc.messages[0], code=exc.code)
    except ValidationError as exc:
        return _json_error(exc.messages[0] if exc.messages else str(exc))

    return _item_response(item)


@catalog_required
@require_POST
def manage_item_bulk(request):
    denied = deny_unless(request, CHANGE_ITEM)
    if denied:
        return denied
    try:
        payload = _parse_json(request)
        action_name = str(payload.get("action", "")).strip()
        if action_name not in {"deactivate", "reactivate"}:
            raise ValidationError("action must be deactivate or reactivate.")
        ids = payload.get("ids")
        if not isinstance(ids, list) or not ids:
            raise ValidationError("ids must be a non-empty list.")
        item_ids = [int(item) for item in ids]
    except (ValidationError, TypeError, ValueError) as exc:
        message = exc.messages[0] if isinstance(exc, ValidationError) and getattr(exc, "messages", None) else str(exc)
        return _json_error(message)

    action = deactivate_item if action_name == "deactivate" else reactivate_item
    reason = str(payload.get("reason", ""))
    items = list(
        Item.objects.filter(pk__in=item_ids).select_related("family")
    )
    found_ids = {item.id for item in items}
    missing = [item for item in item_ids if item not in found_ids]
    if missing:
        return _json_error(f"Item not found: {', '.join(str(entry) for entry in missing)}.", status=404)

    try:
        for item in items:
            action(request.user, item, reason=reason)
    except (DeactivateReasonRequiredError, ReactivateReasonRequiredError) as exc:
        return _json_error(exc.messages[0], code=exc.code)

    refreshed = (
        Item.objects.select_related("family", "vat_rate")
        .filter(pk__in=found_ids)
    )
    logger.info(
        "Console bulk %s ids=%s user=%s",
        action_name,
        item_ids,
        request.user.email,
    )
    return JsonResponse(
        {"items": [_serialize_item(item) for item in refreshed]}
    )


@catalog_required
@require_GET
def manage_item_history(request, item_id):
    try:
        item = Item.objects.get(pk=item_id)
    except Item.DoesNotExist:
        return _json_error("Item not found.", status=404)

    entries = get_item_history(item)
    return JsonResponse(
        {"history": [_serialize_history_entry(entry) for entry in entries]}
    )


def _family_error(exc):
    if isinstance(exc, (FamilyNameRequiredError, DuplicateFamilyNameError)):
        return _json_error(exc.messages[0], code=exc.code)
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message)
    if isinstance(exc, (ObjectDoesNotExist, ValueError, TypeError)):
        return _json_error(str(exc))
    raise exc


@catalog_required
@require_http_methods(["GET", "POST"])
def manage_family_list(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "families": [
                    _serialize_family(family) for family in _families_with_counts()
                ]
            }
        )

    denied = deny_unless(request, ADD_FAMILY)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        is_active = payload.get("is_active", True)
        if not isinstance(is_active, bool):
            raise ValidationError("is_active must be a boolean.")
        family = create_family(
            name=str(payload.get("name", "")),
            is_active=is_active,
            user=request.user,
        )
    except (FamilyNameRequiredError, DuplicateFamilyNameError, ValidationError) as exc:
        return _family_error(exc)

    logger.info("Console created family id=%s user=%s", family.id, request.user.email)
    return _family_response(family)


@catalog_required
@require_http_methods(["GET", "PATCH"])
def manage_family_detail(request, family_id):
    try:
        family = _get_family(family_id)
    except FamilyProduct.DoesNotExist:
        return _json_error("Family not found.", status=404)

    if request.method == "GET":
        return JsonResponse({"family": _serialize_family(family)})

    denied = deny_unless(request, CHANGE_FAMILY)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        fields = {}
        if "name" in payload:
            fields["name"] = str(payload["name"])
        if "is_active" in payload:
            if not isinstance(payload["is_active"], bool):
                raise ValidationError("is_active must be a boolean.")
            fields["is_active"] = payload["is_active"]
        family = update_family(family, user=request.user, **fields)
    except (FamilyNameRequiredError, DuplicateFamilyNameError, ValidationError) as exc:
        return _family_error(exc)

    logger.info("Console updated family id=%s user=%s", family.id, request.user.email)
    return _family_response(family)


@catalog_required
@require_GET
def manage_family_history(request, family_id):
    try:
        family = FamilyProduct.objects.get(pk=family_id)
    except FamilyProduct.DoesNotExist:
        return _json_error("Family not found.", status=404)

    entries = get_family_history(family)
    return JsonResponse(
        {"history": [_serialize_history_entry(entry) for entry in entries]}
    )


def _supplier_error(exc):
    if isinstance(
        exc,
        (
            SupplierNameRequiredError,
            DuplicateSupplierNameError,
            InvalidSupplierEmailError,
        ),
    ):
        return _json_error(exc.messages[0], code=exc.code)
    if isinstance(exc, ValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return _json_error(message)
    if isinstance(exc, (ObjectDoesNotExist, ValueError, TypeError)):
        return _json_error(str(exc))
    raise exc


def _get_supplier(supplier_id):
    return Supplier.objects.get(pk=supplier_id)


def _supplier_response(supplier):
    supplier = _get_supplier(supplier.pk)
    return JsonResponse({"supplier": _serialize_supplier(supplier)})


def _supplier_fields_from_payload(payload, *, creating):
    fields = {}
    if creating or "name" in payload:
        fields["name"] = str(payload.get("name", ""))
    if "contact_name" in payload or creating:
        fields["contact_name"] = str(payload.get("contact_name", ""))
    if "email" in payload or creating:
        fields["email"] = str(payload.get("email", ""))
    if "phone" in payload or creating:
        fields["phone"] = str(payload.get("phone", ""))
    if "notes" in payload or creating:
        fields["notes"] = str(payload.get("notes", ""))
    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            raise ValidationError("is_active must be a boolean.")
        fields["is_active"] = payload["is_active"]
    return fields


@catalog_required
@require_http_methods(["GET", "POST"])
def manage_supplier_list(request):
    if request.method == "GET":
        return JsonResponse(
            {
                "suppliers": [
                    _serialize_supplier(supplier)
                    for supplier in get_suppliers(active_only=False)
                ]
            }
        )

    denied = deny_unless(request, ADD_SUPPLIER)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        fields = _supplier_fields_from_payload(payload, creating=True)
        supplier = create_supplier(
            user=request.user,
            **fields,
        )
    except (
        SupplierNameRequiredError,
        DuplicateSupplierNameError,
        InvalidSupplierEmailError,
        ValidationError,
    ) as exc:
        return _supplier_error(exc)

    logger.info(
        "Console created supplier id=%s user=%s",
        supplier.id,
        request.user.email,
    )
    return _supplier_response(supplier)


@catalog_required
@require_http_methods(["GET", "PATCH"])
def manage_supplier_detail(request, supplier_id):
    try:
        supplier = _get_supplier(supplier_id)
    except Supplier.DoesNotExist:
        return _json_error("Supplier not found.", status=404)

    if request.method == "GET":
        return JsonResponse({"supplier": _serialize_supplier(supplier)})

    denied = deny_unless(request, CHANGE_SUPPLIER)
    if denied:
        return denied

    try:
        payload = _parse_json(request)
        fields = _supplier_fields_from_payload(payload, creating=False)
        supplier = update_supplier(supplier, user=request.user, **fields)
    except (
        SupplierNameRequiredError,
        DuplicateSupplierNameError,
        InvalidSupplierEmailError,
        ValidationError,
    ) as exc:
        return _supplier_error(exc)

    logger.info(
        "Console updated supplier id=%s user=%s",
        supplier.id,
        request.user.email,
    )
    return _supplier_response(supplier)


@catalog_required
@require_GET
def manage_supplier_history(request, supplier_id):
    try:
        supplier = Supplier.objects.get(pk=supplier_id)
    except Supplier.DoesNotExist:
        return _json_error("Supplier not found.", status=404)

    entries = get_supplier_history(supplier)
    return JsonResponse(
        {"history": [_serialize_history_entry(entry) for entry in entries]}
    )
