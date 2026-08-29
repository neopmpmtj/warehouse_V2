from django.http import JsonResponse
from django.views.decorators.http import require_GET

from products.services import get_catalog

from .permissions import active_branch_required
from .services import (
    availability_hint,
    branch_shows_selling_prices,
    get_branch_commercial_mode,
)


def _decimal_string(value):
    return str(value)


def _serialize_branch_item(item, *, show_selling_prices):
    """Branch-catalog row: identity + optional selling prices + availability hint.

    Cost (buying price) and the exact stock quantity are deliberately omitted —
    lock 7 and the plan §8 Slice 2 ("hide cost", "no exact qty in branch UI").
    Selling prices are included only in priced commercial mode (D37).
    """
    row = {
        "id": item.id,
        "internal_code": item.internal_code,
        "description": item.description,
        "unit_of_measure": item.unit_of_measure,
        "family": item.family.name,
        "sub_family": item.sub_family.name if item.sub_family_id else "",
        "vat_rate": _decimal_string(item.vat_rate.rate),
        "availability": availability_hint(item),
    }
    if show_selling_prices:
        row["retail_price"] = _decimal_string(item.retail_price)
        row["wholesale_price"] = _decimal_string(item.wholesale_price)
        row["special_price"] = _decimal_string(item.special_price)
    return row


@active_branch_required
@require_GET
def branch_catalog_list(request):
    items = get_catalog(active_only=True)
    show_prices = branch_shows_selling_prices()
    return JsonResponse(
        {
            "commercial_mode": get_branch_commercial_mode(),
            "show_selling_prices": show_prices,
            "catalog": [
                _serialize_branch_item(item, show_selling_prices=show_prices)
                for item in items
            ],
        }
    )
