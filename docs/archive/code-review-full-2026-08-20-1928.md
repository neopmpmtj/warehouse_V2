# CentCompras — Full-Codebase Stability Review (read-only)

> **✅ CONCLUDED 20 August 2026, 19:44 WEST — all code findings resolved and fixes applied.** Actionable findings #1–#8, #12, #13, and #14 are fixed; #9/#10/#11 are deferred (commit on the user's side / deploy-time env / catalogue scale — not defects). This review is archived; do not re-implement. Current product state: [`handoff.md`](handoff.md).

> **Read-only review.** No code was changed, no migrations run, nothing deleted. The only write is this report. The codebase was reviewed **as it currently exists on disk**, including the uncommitted Phase 4 (manager catalog) work and the `reopen` transition in the working tree (`git branch phase3-stock-ledger`, ~20 modified files + 5 untracked files).

- **Date:** 20 August 2026
- **Branch:** `phase3-stock-ledger` (Phase 4 manager catalog is uncommitted in the working tree)
- **Test baseline:** `.venv/bin/python manage.py test products accounts procurement inventory --noinput` → **193 tests, OK** (~28.8s).
- **Static checks:** `node --check` clean on all 8 JS bundles (`catalog.js`, `console.js`, `catalog_i18n.js`, `console_i18n.js`, `purchase_orders.js`, `purchase_orders_i18n.js`, `goods_receipts.js`, `goods_receipts_i18n.js`). `grep -rn "innerHTML|outerHTML|insertAdjacentHTML|document.write|eval("` across `products/ procurement/ inventory/ accounts/` (`.js` + `.html`) → **zero matches**.
- **Prior reviews consulted (to avoid re-reporting fixed items):** `docs/archive/code-review-audit.md`, `docs/archive/code-review-2026-08-20.md`, `docs/archive/code-review-inventory-2026-08-20.md`.

---

## Summary

Phases 0–4 are well-architected and follow the house conventions consistently: all mutations funnel through `services.py`, `@transaction.atomic` + `select_for_update()` guard the money path, the stock ledger is append-only with `Item.quantity` written *only* in `_write_movement`, audit-by-design is applied everywhere, admin is superuser-only, CSRF is on (no `csrf_exempt`), and the frontend renders exclusively via `textContent`/`createElement` (zero `innerHTML`). The Phase 3 inventory review's findings are all genuinely fixed, and the new `reopen` transition and manager catalog are correctly implemented and well-tested.

I found **no 🔴 High-severity (data-loss / corruption / security) defect**. The findings are **medium/low severity**, and the single most notable one is a *recurring* robustness gap: the inventory app already hardened its quantity parser against non-finite input (`NaN`/`Infinity`) with a `DecimalException` backstop, but **procurement** (`quantity`/`unit_cost`/discounts) and **products supplier-price `cost_price`** still parse with bare `Decimal(str(...))` + comparison, so a crafted `NaN` produces an unhandled `decimal.InvalidOperation` → **HTTP 500** instead of a clean 400. It fails safe (nothing is written), but it's reachable by any authenticated manager/admin via `curl` and is the exact class of bug the user has hit repeatedly.

> An independent orchestrator review (run in parallel) corroborated all ten findings above and added #11–#13 below; the user reported #14 during review.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| 1 | 🟡 Medium | Backend / API (procurement) | `NaN` in PO line `quantity`/`unit_cost`/discounts → unhandled `InvalidOperation` → 500 (not 400) |
| 2 | 🟡 Medium | Backend / API (products) | `NaN` supplier-price `cost_price` → unhandled `InvalidOperation` → 500 (not 400) |
| 3 | 🟢 Low | Backend / query | PO list view N+1 on `approved_by` (missing `select_related`) |
| 4 | 🟢 Low | Backend / API | Malformed `?family_id=` / `?item_id=` query params → unhandled `ValueError`/`DoesNotExist` → 500 |
| 5 | 🟢 Low | Backend / business rule | `adjust_stock` permits negative stock balance with no guard/warning |
| 6 | 🟢 Low | Frontend | `console.js` `formatCost` still uses `Number().toFixed(2)` (inconsistent with other consoles) |
| 7 | 🔵 Info | Frontend / i18n | `unitCostHint` text contradicts D12 ("defaults to 0" vs "rejected") |
| 8 | 🔵 Info | Backend | Dead code: `suggested_supplier()`, `get_item_buying_price()` |
| 9 | 🔵 Info | Migration / repo | `inventory/0002` migration + whole Phase 4 are uncommitted (untracked) |
| 10 | 🔵 Info | Config | `DEBUG` defaults to `True`; `ALLOWED_HOSTS` localhost-only (dev-only) |
| 11 | 🔵 Info | Backend / scale | Manager catalog returns all rows with no pagination (item console already paginates) |
| 12 | 🔵 Info | Backend / perms | Admins granted `delete_goodsreceipt` but there is no delete path (append-only) |
| 13 | 🟢 Low | Backend / business | Catalog buying price ignores supplier `is_active` (deactivated supplier's price still shows) |
| 14 | 🟡 Medium | Frontend (inventory) | Item filter dropdown never populates (init race) |

---

## Fix status (20 August 2026)

Test suite went **193 → 199 tests, green** after the first fix pass. All findings below are resolved except the three deferred/hygiene items.

| # | Status |
|---|--------|
| 1 | ✅ FIXED — shared finite-aware `_parse_decimal` in procurement + `DecimalException` backstop |
| 2 | ✅ FIXED — `_validate_cost_price` rejects non-finite; `DecimalException` backstop |
| 3 | ✅ FIXED — `approved_by` added to `select_related` |
| 4 | ✅ FIXED — `try/except` → 400 on malformed `family_id`/`item_id` |
| 5 | ✅ FIXED — negative-balance adjustment rejected (`NegativeStockError`) |
| 6 | ✅ FIXED — `console.js` `formatCost` now string-based |
| 7 | ✅ FIXED — `unitCostHint` corrected to match D12 |
| 8 | ⚠️ PARTIAL — `suggested_supplier` removed; `get_item_buying_price` kept (tested single-item utility) |
| 9 | ⏳ Open — uncommitted migration + Phase 4 (commit with the model/migration pair) |
| 10 | ⏸ Deferred — deploy-time env (`DJANGO_DEBUG=false`, real secret, `ALLOWED_HOSTS`) |
| 11 | ⏸ Deferred — catalogue pagination (small scale today) |
| 12 | ✅ FIXED — `goodsreceipt` excluded from the `delete_*` grant |
| 13 | ✅ FIXED — deactivated suppliers excluded from buying price + suppliers list |
| 14 | ✅ FIXED — `await loadItems()` before `fillItemFilter()`; filter refreshed in `openAdjustDialog` |

---

## Findings

### 1. 🟡 `NaN` quantity/unit_cost/discount in procurement → 500

**Files:** `procurement/services.py` (`_validate_quantity` L93, `_validate_unit_cost` L100, `_validate_discount` L107; called from `add_line` L190–203 and `update_line` L261–265), `procurement/console_views.py` (`_parse_decimal` L44, `except ValidationError` at L198 / L240 / L264 / L275).

`_parse_decimal` only guards `Decimal(str(x))` against `InvalidOperation/TypeError/ValueError` and does **not** check finiteness, so `"NaN"` parses to `Decimal("NaN")` and flows into the service. There, `_validate_quantity` does `Decimal(str(NaN))` then `if value <= 0` — and `Decimal("NaN") <= 0` **raises `decimal.InvalidOperation`** (verified). `_validate_unit_cost` (`value < 0`) and `_validate_discount` (`amount < 0`) raise the same way for `NaN`.

`decimal.InvalidOperation` is a subclass of `ArithmeticError`, **not** `ValueError`, so none of the console view's `except ValidationError` (nor `_po_error`'s `(ObjectDoesNotExist, ValueError, TypeError)`) catches it → the request ends as an **unhandled 500**.

Reachable by any authenticated manager/admin (`CHANGE_PO`) with e.g. `POST /api/manage/purchase-orders/<id>/lines/` body `{"item_id": <valid>, "quantity": "NaN"}` (the `_validate_quantity` call happens *before* the supplier-price check, so no price is needed). `"Infinity"` does **not** 500 here — it passes the `<= 0` guard and is then rejected by `line.full_clean()` (400) — so the trigger is specifically `NaN`.

This is the *same class* the inventory review already fixed (its #1) with `_parse_decimal_quantity()` + a `DecimalException` backstop, but procurement was never given the same hardening.

**Suggested fix:** add a shared guarded parser (mirror `inventory/services.py:_parse_decimal_quantity`) that rejects non-finite values and quantises/bounds, use it in `_validate_quantity`/`_validate_unit_cost`/`_validate_discount`, and add `decimal.DecimalException` to the view's `except` tuple as a final backstop.

---

### 2. 🟡 `NaN` supplier-price `cost_price` → 500

**Files:** `products/services.py` (`_validate_cost_price` L741), `products/console_views.py` (`_parse_decimal` L189; `manage_supplier_item_price_list` POST `except (DuplicateSupplierItemPriceError, InvalidCostPriceError, ValidationError)`; `_supplier_item_price_error`).

Same root cause as #1: `_validate_cost_price` does `Decimal(str(x))` then `if value < 0`, so `cost_price: "NaN"` raises `decimal.InvalidOperation` (verified), which is not caught by the supplier-price view's `except` clauses nor by `_supplier_item_price_error` (which only handles `(ObjectDoesNotExist, ValueError, TypeError)`) → **500**.

Reachable by any user with `ADD_SUPPLIER_ITEM_PRICE` (admin/manager) via `POST /api/manage/supplier-prices/` with `{"supplier_id": …, "item_id": …, "cost_price": "NaN"}`. `"Infinity"` is caught by `full_clean` (400), so again the trigger is `NaN`.

Note the item pricing fields (`reorder_level`/`retail_price`/`wholesale_price`/`special_price`) are *not* affected because they go through `_save_item`'s `full_clean`, which turns `NaN` into a `ValidationError` (400). Only `cost_price` (which does a bare comparison before `full_clean`) is exposed.

**Suggested fix:** reuse the same finite-aware parser (or at least `if not value.is_finite(): raise InvalidCostPriceError()`) in `_validate_cost_price`, and add `decimal.DecimalException` to `_supplier_item_price_error`.

---

### 3. 🟢 PO list view N+1 on `approved_by`

**Files:** `procurement/services.py` (`get_purchase_orders` L496 does `select_related("supplier", "created_by")`), `procurement/console_views.py` (`_serialize_po` L78 accesses `po.approved_by.email`).

`manage_purchase_order_list` (GET) serialises every PO with `_serialize_po(po, include_lines=False)`, which reads `po.approved_by.email if po.approved_by_id else None`. `approved_by` is **not** in `select_related`, so every approved/received/closed PO in the list triggers one extra query for its approver. Draft POs don't (no `approved_by_id`), but a list dominated by approved POs issues ~N extra queries. The detail view (`_get_po`) already selects `approved_by`, so it's unaffected.

**Suggested fix:** add `"approved_by"` to `get_purchase_orders`'s `select_related`.

---

### 4. 🟢 Malformed query params on catalog / stock-movements → 500

**Files:** `products/console_views.py` (`manage_catalog_list` L879, no try/except), `products/services.py` (`get_catalog` L928 → `_resolve_family` L140), `inventory/console_views.py` (`manage_stock_movements` L198, no try/except), `inventory/services.py` (`get_stock_movements` L298).

- `GET /api/manage/catalog/?family_id=abc` → `_resolve_family("abc")` → `FamilyProduct.objects.get(pk="abc")` raises `ValueError` (verified). `?family_id=999999` raises `FamilyProduct.DoesNotExist`. Neither is caught → **500**.
- `GET /api/manage/stock-movements/?item_id=abc` → `StockMovement.objects.filter(item="abc")` raises `ValueError` at evaluation (verified) → **500**.

Both endpoints are authenticated `@require_GET` reads, so this is a robustness/500 issue, not a data-integrity one.

**Suggested fix:** wrap both in a `try/except (ValueError, ObjectDoesNotExist)` returning a 400 (or validate `int()` up front like the supplier-price list endpoint already does).

---

### 5. 🟢 `adjust_stock` allows a negative stock balance (no guard)

**Files:** `inventory/services.py` (`adjust_stock` L264), `inventory/static/inventory/js/goods_receipts.js` (`submitAdjustment`).

`adjust_stock` accepts any signed finite quantity and writes it as a signed `StockMovement`, updating cached `Item.quantity` with no lower-bound check. An admin typo (e.g. `-5000` instead of `-50`) drives the cached balance negative with no confirmation or warning; the manager catalog then shows a negative `quantity` and flags it `below_reorder`. The ledger and cache stay consistent (both go negative together), so this is **not corruption**, but there is no business rule preventing or flagging negative stock — the review checklist explicitly calls this edge case out, and it is currently undecided.

**Suggested fix:** decide the policy and either (a) reject adjustments that would make `quantity < 0` (with a clear error code), or (b) keep negative stock but add a client-side/back-end warning and a confirm dialog for large removals.

---

### 6. 🟢 `console.js` `formatCost` still uses `Number().toFixed(2)`

**Files:** `products/static/products/js/console.js` (`formatCost`), used by `renderItemSupplierPrices`.

The prior Phase-2 review fixed `formatCost`/`formatPercent` in `purchase_orders.js` to use string manipulation (no `Number()`), and `catalog.js` does the same. `console.js` still has `Number(value).toFixed(2)` for supplier-price display. At `Decimal(12,2)` magnitudes this is harmless (well under 2^53), but it's the wrong tool for money and inconsistent with the rest of the codebase.

**Suggested fix:** replace with the same string-based formatter used in `purchase_orders.js`.

---

### 7. 🔵 Stale i18n hint contradicts D12

**Files:** `procurement/static/procurement/js/purchase_orders_i18n.js` (`unitCostHint`, en + pt-PT).

The hint reads *"Leave blank to auto-fill from the supplier price list (defaults to 0 if the item has no supplier price)."* But locked decision **D12** (and `add_line`) is that a PO line is **rejected** if the supplier has no price for the item (`SupplierPriceMissingError`). The "(defaults to 0 …)" clause is wrong and will mislead users. (The pt-PT translation repeats the same wrong clause.)

**Suggested fix:** update both strings to say the line is rejected when the supplier has no price (and add the supplier price under Suppliers → Supplier prices first).

---

### 8. 🔵 Dead code

**Files:** `procurement/services.py` (`suggested_supplier` L130), `products/services.py` (`get_item_buying_price` L922).

- `suggested_supplier()` is never called (the console does not auto-suggest the primary supplier today; D11 says "later").
- `get_item_buying_price()` is only referenced by `products/tests.py`; the catalog path uses the equivalent `catalog_buying_price()` (prefetch-aware). It's effectively a duplicate with no production caller.

Neither is harmful; they're harmless leftovers worth deleting or wiring up.

**Suggested fix:** remove, or wire `suggested_supplier` into the new-PO dialog if D11 auto-suggest is wanted.

---

### 9. 🔵 Uncommitted migration + Phase 4 (repo hygiene)

**Files:** `inventory/migrations/0002_stockmovement_stockmovement_reference_both_or_neither.py` (untracked), plus the entire Phase 4 manager catalog (`catalog.html`, `catalog.js`, `catalog_i18n.js`, `catalog.css` untracked) and the `reopen` transition (modified, uncommitted).

Per `git status`: 20 modified files and 5 untracked files (including the new `inventory/0002` migration). A fresh clone will not have the `stockmovement_reference_both_or_neither` check constraint, and `makemigrations --check` will report drift. This is a review-time observation, not a code defect — but the migration **must be committed together with** the model change.

**Suggested fix:** commit the working tree (or at least the migration + model/constraint pair) before any deploy.

---

### 10. 🔵 Dev-only settings defaults

**Files:** `config/settings.example.py` (`SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`).

`DEBUG` defaults to `True` and `ALLOWED_HOSTS = ["localhost", "127.0.0.1"]` unless env vars are set; `SECRET_KEY` falls back to `"change-me-in-production"`. Production deployment/OAuth is explicitly deferred (Phase 7), so this is expected — but any "production-ready" claim must gate on env-driven values.

**Suggested fix:** keep as-is for now; enforce `DJANGO_DEBUG=false` + real `DJANGO_SECRET_KEY` + `ALLOWED_HOSTS` at deploy time.

---

### 11. 🔵 Manager catalog has no pagination

**File:** `products/console_views.py` (`manage_catalog_list` L879), `products/services.py` (`get_catalog` L925).

`get_catalog()` returns every active item in one response (no `?page`/`?page_size`), and `catalog.js` filters/sorts client-side. The item console already supports server pagination (`_console_payload`, audit #8). Fine at the current ~60-item scale, but it grows linearly and re-imports the exact limitation the catalogue console already fixed.

**Suggested fix:** add the same `page`/`page_size` clamping used by `_console_payload`, or document that the catalogue is intentionally small and pagination is deferred.

*(Added by the orchestrator's parallel review.)*

---

### 12. 🔵 Admins are granted `delete_goodsreceipt` but no delete path exists

**File:** `accounts/groups.py` (`CATALOG_MODELS` includes `"goodsreceipt"`; `_codenames_for_group` grants `delete_*` to admins).

`GoodsReceipt` is append-only by design (no delete endpoint, no delete UI, admin read-only). But because `"goodsreceipt"` is in `CATALOG_MODELS`, the `warehouse_admins` group gets `inventory.delete_goodsreceipt` — a permission with no code path to exercise. Harmless, but misleading.

**Suggested fix:** move `"goodsreceipt"` out of the `delete_*` grant (keep add/change, drop delete), or document it as intentionally-granted-but-unused.

*(Added by the orchestrator's parallel review.)*

---

### 13. 🟢 Catalog buying price ignores supplier `is_active`

**File:** `products/services.py` (`_buying_price_from_prices`, `catalog_buying_price`).

`catalog_buying_price` prefers the `primary` price, else cheapest, with no filter on `Supplier.is_active`. If the primary supplier is deactivated (soft-delete), their `SupplierItemPrice` still surfaces as the item's "buying price" in the manager catalog. This is pre-existing behaviour (the older `get_item_buying_price` does the same), so not a regression — but it's an undecided business rule worth a deliberate answer.

**Suggested fix:** decide whether deactivated suppliers' prices should count; if not, filter `supplier__is_active=True` in the buying-price resolution and the suppliers list.

*(Added by the orchestrator's parallel review.)*

---

### 14. 🟡 Item filter dropdown never populates (init race)

**File:** `inventory/static/inventory/js/goods_receipts.js` (`init`, `fillItemFilter`, `loadItems`, `openAdjustDialog`).

`init()` calls `loadItems()` **without awaiting** it, then awaits `Promise.all([loadReceipts(), loadMovements()])` and immediately calls `fillItemFilter()`. Because the items request is usually slower than the lighter receipts/movements requests, `state.items` is still empty when `fillItemFilter()` runs, so the "Item filter" dropdown on the Stock movements table is built with only the "All items" placeholder. `fillItemFilter()` is never called again, and `openAdjustDialog` (which later calls `loadItems()` and populates the *adjust* select) does not refresh the movements filter — so the movements filter stays stuck on "All items".

**Suggested fix:** `await loadItems()` before `fillItemFilter()` (or run `fillItemFilter()` in `loadItems().then(...)`), and have `openAdjustDialog` also re-run `fillItemFilter()` once items are loaded.

*(Reported by the user during review — not caught by either reviewer.)*

---

## Verified-correct (checked, no issue)

- **Stock ledger integrity** — `Item.quantity` is written **only** in `_write_movement` (`inventory/services.py` L151); it is absent from `products/services.ITEM_UPDATABLE_FIELDS`, absent from `console.js` `formPayload()`, and read-only in `ItemAdmin`. Movement insert + balance update share one transaction, so cache and ledger cannot diverge.
- **Concurrency** — `receive_goods` locks the PO first (`select_for_update()`), then computes `_received_qty_map()` under that lock, so concurrent receipts for the same PO serialize and cannot over-receive (covered by `test_concurrent_receipts_cannot_over_receive` and `test_receive_goods_locks_rows_for_update`). `_write_movement` locks the `Item`; lock ordering is consistent (PO → items) with no reverse cycle vs `adjust_stock` (item only).
- **Receipt validation** — the inventory review's #1/#2/#5/#6 fixes are genuinely present: `_parse_decimal_quantity()` rejects non-finite, rounds-to-zero, and oversized values (bound `1e9`, quantise `0.001`); duplicate `line_id`s and non-dict lines are rejected with clear codes; `_received_qty_map()` is a single grouped aggregate; the `DecimalException` backstop is in both `_inv_error` and the `except` tuples.
- **Stock movement reference** — `StockMovement` now has the `stockmovement_reference_both_or_neither` `CheckConstraint` (model + migration `0002`), and `_serialize_movement` surfaces a `reference` (`GR #…` or a generic `contenttype #id` fallback), bulk-resolved via one `GoodsReceipt` query.
- **`adjust_stock` response contract** — now returns the `StockMovement` and responds with `quantity` (delta) + `balance` (new total), fixing the old "balance masquerading as delta" bug.
- **PO state machine incl. `reopen`** — `STATUS_TRANSITIONS` enforces order (draft→submitted→approved→received→closed, submitted→rejected, rejected→draft); `reopen()` is `@transaction.atomic`, locks the row, writes a `STATUS_CHANGED` audit, and is permission-gated (`CHANGE_PO`) + tested (`test_reopen_rejected_returns_to_draft_and_resubmit`, `test_reopen_non_rejected_is_invalid`, `test_reopen_rejected_po_through_api`). Rejected POs can never carry stale `approved_*` data (reject only from `submitted`).
- **O1 buying price** — `_buying_price_from_prices` correctly prefers `primary`, else cheapest, else `None`; `catalog_buying_price` reuses prefetched prices (no extra query); `catalog_below_reorder` correctly ignores `reorder_level == 0`.
- **VAT math** — `VatRate.rate` stores the fraction (e.g. `0.16`), and `line_vat = line_net * vat_rate` (quantised to 0.01); approved totals are snapshotted once at `approve()` (D13).
- **Discount validation** — per-field 0–100 **and** combined ≤ 100, both on add and update, with regression tests.
- **Permission defence-in-depth** — backend `deny_unless` + service checks; frontend `data-can-*` flags hide write UI; admin is superuser-only (`SuperuserAdminSite` + per-model `has_*_permission` returning `is_superuser`); no `csrf_exempt`; APIs return 401 unauth / 403 forbidden. Operators are read-only throughout (tested).
- **XSS / CSRF / serialisation** — zero `innerHTML` (grep-verified); `{{ user.email }}` auto-escaped; `X-CSRFToken` from the meta tag; Decimals serialised as strings everywhere.
- **Catalog query efficiency** — `get_catalog` uses `select_related("family", "vat_rate")` + `prefetch_related("supplier_prices__supplier")`, so `_serialize_catalog_item` causes no N+1 (verified against the prefetch usage).
- **Double-submit / request-id guards** — `state.busy` + button disable across all async mutation paths; request-id guards on all history/detail loads; safe `localStorage` helpers.

---

## Recommended priority

1. **#1 and #2** (NaN → 500 in procurement and supplier-price `cost_price`) — the one real robustness gap; the same class already fixed in inventory, cheap to close with a shared finite-aware parser + a `DecimalException` backstop.
2. **#4** (malformed query params → 500) — trivial `try/except` around the two `@require_GET` endpoints.
3. **#14** (item-filter dropdown init race) — `await loadItems()` before `fillItemFilter()`; refresh the filter in `openAdjustDialog`.
4. **#3** (PO list `approved_by` N+1) — one-line `select_related` addition.
5. **#5** (negative-stock policy) — decide the business rule and add a guard or a confirm/warning.
6. **#6, #7** — cheap polish (string-based `formatCost`, fix the misleading `unitCostHint`).
7. **#8, #9, #10** — cleanup/hygiene: remove dead code, commit the migration + Phase 4, document deploy-time env requirements.
8. **#11–#13** — minor/deferred: catalogue pagination, `delete_goodsreceipt` grant, inactive-supplier pricing policy.
