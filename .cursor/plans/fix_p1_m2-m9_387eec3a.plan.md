---
name: Fix P1 M2-M9
overview: "Implement P1 from the live review: D12 re-check at submit, inactive-entity lifecycle rules, reject duplicate PO lines, and API/quantity robustness. Then run the full suite the fast way and mark M2, M3, M4, M9 done in the tracker."
todos:
  - id: m3-submit-prices
    content: Re-validate supplier prices on submit and approve; add tests
    status: completed
  - id: m2-inactive-lifecycle
    content: Block inactive supplier/item/family on PO + catalog + create/update item; add tests
    status: completed
  - id: m4-unique-po-line
    content: UniqueConstraint + DuplicatePOLineError on add_line; migration + tests
    status: completed
  - id: m9-api-overflow
    content: Catch missing item_id, strict int IDs, stock balance cap; add tests
    status: completed
  - id: p1-fast-suite
    content: Run full suite with --keepdb --noinput; mark M2/M3/M4/M9 done in tracker
    status: completed
isProject: false
---

# Fix P1 (M3, M2, M4, M9)

Same shape as [`.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md`](.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md): service-layer rules, targeted `TestCase` tests, `--keepdb --noinput`, then mark the tracker. Do **not** archive the review doc.

**Locked policy (this session):**

- **M4:** reject duplicate item on a PO (`UniqueConstraint` + service `ValidationError`). Do **not** merge quantities.
- **M2:** full lifecycle — inactive supplier/item blocked on POs; manager catalog excludes items whose family is inactive; `create_item` / `update_item` cannot assign an inactive family.

Leave M1, M5–M8, M10, L* untouched.

**Tests:** `.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput`. Use `django.test.TestCase` (rollback). No extra `TransactionTestCase`. If `--keepdb` is stale after a failed run, recreate once with `--noinput` (no `--keepdb`).

---

## M3 — Re-check supplier prices at submit (D12)

**Bug:** [`add_line`](procurement/services.py) looks up `SupplierItemPrice` for `(po.supplier, item)`. [`submit`](procurement/services.py) only checks “has lines”. If the price row is deleted while the PO is still draft, submit/approve succeed and D12 is bypassed.

**Fix in** [`procurement/services.py`](procurement/services.py):

- `_line_has_supplier_price(po, item)` — same filter as `add_line`.
- `_validate_all_lines_have_supplier_price(po)` — walk `po.lines.select_related("item")`; raise existing `SupplierPriceMissingError` (include item id/description in the message if easy).
- Call it from `submit()` after the empty-lines check, **before** `_transition`.
- Also call it from `approve()` (cheap second gate between submit and freeze of D13 totals).

**Tests in** [`procurement/tests.py`](procurement/tests.py):

- Add line, delete that `SupplierItemPrice`, `submit` → `SupplierPriceMissingError`.
- Same setup, submit with price present, delete price, `approve` → `SupplierPriceMissingError`.
- Happy path submit/approve still works.

---

## M2 — Inactive catalogue entities (full lifecycle)

**Bug:** [`create_purchase_order`](procurement/services.py) / `add_line` / `submit` ignore `supplier.is_active` and `item.is_active`. [`create_item`](products/services.py) / [`update_item`](products/services.py) accept an inactive family. [`get_catalog`](products/services.py) filters item activity only, so live items under a deactivated family still appear.

**Procurement** ([`procurement/services.py`](procurement/services.py)):

- Dedicated errors with codes, e.g. `InactiveSupplierError` (`inactive_supplier`), `InactiveItemError` (`inactive_item`).
- `create_purchase_order`: after `_resolve_supplier`, reject if `not supplier.is_active`.
- `add_line`: after `_resolve_item`, reject if `not item.is_active`.
- `submit()` (and `approve()`): supplier still active; every line’s item still active; then M3 price check.

Do **not** cascade-deactivate items when a family is deactivated (out of scope; catalog filter + assign block is enough).

**Products** ([`products/services.py`](products/services.py)):

- `_ensure_family_active(family)` — raise a small `ValidationError` (`inactive_family`) if `not family.is_active`.
- Call after `_resolve_family` in `create_item` and when `update_item` changes `family`.
- `get_catalog(active_only=True)`: also `.filter(family__is_active=True)`.

**Tests:**

- Procurement: inactive supplier cannot create PO; inactive item cannot `add_line`; deactivate item (or supplier) after draft lines → `submit` rejected.
- Products: `create_item` / `update_item` to inactive family rejected; `get_catalog()` omits an active item whose family was deactivated; existing catalog tests still pass for active families.

---

## M4 — Reject duplicate PO lines

**Bug:** [`PurchaseOrderLine`](procurement/models.py) has no uniqueness on `(purchase_order, item)`. [`add_line`](procurement/services.py) always inserts a new row.

**Fix:**

1. [`procurement/models.py`](procurement/models.py):

```python
models.UniqueConstraint(
    fields=["purchase_order", "item"],
    name="unique_po_line_item",
)
```

2. Migration `procurement/0004_...` via `makemigrations`. If existing duplicate rows exist, the migration will fail — inspect with a one-off query before applying; seed/dev data is not expected to have duplicates. No merge/backfill unless we find rows.

3. [`procurement/services.py`](procurement/services.py) — `DuplicatePOLineError` (`duplicate_po_line`). In `add_line`, after lock + draft + item resolve, if `po.lines.filter(item=item).exists()` raise it (clean 400 before `IntegrityError`). Map `IntegrityError` on line save to the same error as defence in depth (same pattern as supplier prices).

**Tests:** second `add_line` of the same item → `DuplicatePOLineError`; different items still OK; ORM bypass two rows → `IntegrityError`.

---

## M9 — API and quantity robustness

### Bad `item_id` → 500

[`manage_purchase_order_lines` POST](procurement/console_views.py) only `except ValidationError`. `_resolve_item` raises `Item.DoesNotExist`. [`_po_error`](procurement/console_views.py) already maps `ObjectDoesNotExist`.

**Fix:** catch `(ValidationError, ObjectDoesNotExist, ValueError, TypeError, DecimalException)` like list-create (L168). Return 404 for missing item (`"Item not found."`) if easy; 400 is acceptable if `_po_error` already stringifies `DoesNotExist`.

### `int(1.9)` truncates IDs

[`int(supplier_id)`](procurement/console_views.py) / `int(item_id)` silently coerce floats.

**Fix:** helper `_parse_int_id(value, field_name)` — accept `int` or digit string; reject `bool`, `float`, empty, non-integers with `ValidationError`. Use for `supplier_id` and `item_id`.

### Cumulative stock overflow

[`_parse_decimal_quantity`](inventory/services.py) caps a **movement** at `< 1e9`. [`_write_movement`](inventory/services.py) does `new_quantity = item.quantity + quantity` with no check against `DecimalField(max_digits=12, decimal_places=3)` (max `999999999.999`).

**Fix:** after computing `new_quantity`, if `new_quantity.copy_abs() >= Decimal("1000000000")` raise `InvalidQuantityError` with a clear message (before `item.save`).

**Tests:**

- Procurement console: POST add-line with unknown `item_id` → 400/404 not 500; `"item_id": 1.9` → 400.
- Inventory: stock near the cap + receipt/adjust that would overflow → `InvalidQuantityError`; existing oversize movement tests still pass.

---

## After tests pass

Update [`docs/code-review-full-2026-08-20-2208.md`](docs/code-review-full-2026-08-20-2208.md):

- Per-finding **Status** lines for M2, M3, M4, M9 → Done (one-line what landed).
- Tracker table: those four IDs → Done.
- Leave H1–H3 Done; M1/M5–M8/M10/L* unchanged. Do not archive.

Run:

```bash
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```
