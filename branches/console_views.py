from django.http import JsonResponse
from django.views.decorators.http import require_GET

from logging_utils import get_logger

from products.services import get_catalog

from .permissions import active_branch_required
from .services import availability_hint

logger = get_logger("centcompras.branches")


def _decimal_string(value):
    return str(value)


def _serialize_branch_item(item):
    """Branch-catalog row: identity + selling prices + availability hint.

    Cost (buying price) and the exact stock quantity are deliberately omitted —
    lock 7 and the plan §8 Slice 2 ("hide cost", "no exact qty in branch UI").
    """
    return {
        "id": item.id,
        "internal_code": item.internal_code,
        "description": item.description,
        "unit_of_measure": item.unit_of_measure,
        "family": item.family.name,
        "sub_family": item.sub_family.name if item.sub_family_id else "",
        "vat_rate": _decimal_string(item.vat_rate.rate),
        "retail_price": _decimal_string(item.retail_price),
        "wholesale_price": _decimal_string(item.wholesale_price),
        "special_price": _decimal_string(item.special_price),
        "availability": availability_hint(item),
    }


@active_branch_required
@require_GET
def branch_catalog_list(request):
    items = get_catalog(active_only=True)
    return JsonResponse(
        {"catalog": [_serialize_branch_item(item) for item in items]}
    )
