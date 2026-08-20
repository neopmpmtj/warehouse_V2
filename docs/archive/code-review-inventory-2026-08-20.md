# CentCompras — Code Review (Phase 3: goods receipt + stock ledger)

> **✅ CONCLUDED — all findings resolved.** Product Phase 3 (goods receipt + stock ledger) **is done**, and every numbered finding below (#1–#9) was **applied** in the Phase 3 follow-up. This file is now a **historical record**, not a backlog — do **not** re-implement the findings. **Conclusion: 20 August 2026, 17:50 WEST.** Current product state: [`handoff.md`](../handoff.md).

> Read-only review. Scope: the new `inventory` app plus its cross-cutting changes to `procurement`, `products`, `accounts`, and `config`. No code was changed during this review.

- **Date:** 20 August 2026
- **Branch:** `phase3-stock-ledger`
- **Test baseline:** `.venv/bin/python manage.py test inventory procurement products accounts --noinput` → **170 tests, OK** (~16s). `node --check` clean on `goods_receipts.js`, `goods_receipts_i18n.js`, and `purchase_orders.js`. Zero `innerHTML` in the new JS/templates.

---

## Summary

The Phase 3 implementation is **well-architected and follows the house conventions** (service layer, `@transaction.atomic` + `select_for_update()`, append-only ledger, audit-by-design, read-only admin, defence-in-depth permissions). The core money path — `receive_goods()` writing receipt → movement → cached `Item.quantity` → driving PO `approved → received → closed` — is **correct**, and I found **no High-severity (data-loss/corruption) defects**. Concurrency is handled properly: the PO row is locked first and item rows are locked in `_write_movement`, so concurrent receipts/adjustments are serialised and cannot over-receive or lose updates.

The findings are **medium/low severity**, concentrated in one area: **input validation in the JSON API**. The service layer parses quantities with bare `Decimal(str(...))` and the console view's `except` clause omits `decimal.InvalidOperation`/`DecimalException`, so malformed or non-finite quantities (`"abc"`, `"NaN"`, `"Infinity"`) and duplicate line ids produce an unhandled **500** instead of a clean **400**. These are reachable by any authenticated manager/admin via `curl`, but they fail safe (transaction rollback) rather than corrupting stock.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| 1 | 🟡 Medium | Backend / API | Malformed & non-finite quantities → unhandled 500 (not 400) |
| 2 | 🟡 Medium | Backend / API | Duplicate `line_id`s in a receipt → `IntegrityError` → 500; over-receipt only backstopped by the DB unique constraint |
| 3 | 🟢 Low | Backend / API | `adjust_stock` returns the item; response `quantity` is the new *balance*, not the *delta* |
| 4 | 🟢 Low | Backend / UI | Receipt stock movements aren't traceable back to their `GoodsReceipt` in the UI |
| 5 | 🟢 Low | Backend | `get_receipt_summary` issues one aggregate query per line (N+1) |
| 6 | 🟢 Low | Backend | No `decimal_places`/`max_digits` validation → silent rounding or `DataError` on oversized/over-precise quantities |
| 7 | 🔵 Info | Backend | `StockMovement` GenericForeignKey has no DB-level "both-or-neither" guarantee |
| 8 | 🔵 Info | Frontend | Orphaned `actionReceive` i18n keys in `purchase_orders_i18n.js` |
| 9 | 🔵 Info | Tests | No concurrency/race-coverage test for the locking logic |

---

## Fix status — concluded 20 August 2026, 17:50 WEST

All nine findings were fixed in the Phase 3 follow-up. The test suite went **170 → 181 tests, all green**. This file is a historical record; do not re-implement.

| # | Severity | Status |
|---|----------|--------|
| 1 | 🟡 Medium | ✅ FIXED — guarded `_parse_decimal_quantity()` (try/except + `is_finite()`); `DecimalException` backstop in the API |
| 2 | 🟡 Medium | ✅ FIXED — duplicate `line_id` detection (`DuplicateReceiptLineError`) + dict/key validation (`InvalidReceiptLineError`) |
| 3 | 🟢 Low | ✅ FIXED — `adjust_stock` returns the `StockMovement`; API returns `quantity` (delta) + `balance` (new total) |
| 4 | 🟢 Low | ✅ FIXED — movements serialise a `reference` (`GR #…`), bulk-resolved; "Reference" column added |
| 5 | 🟢 Low | ✅ FIXED — single grouped `_received_qty_map()` aggregate replaces per-line `Sum` |
| 6 | 🟢 Low | ✅ FIXED — quantities quantised to `0.001`, rejected if they round to zero or exceed `max_digits` |
| 7 | 🔵 Info | ✅ FIXED — `CheckConstraint` `stockmovement_reference_both_or_neither` + migration `0002` |
| 8 | 🔵 Info | ✅ FIXED — orphaned `actionReceive` keys removed |
| 9 | 🔵 Info | ✅ FIXED — `CaptureQueriesContext` lock test + two-thread `TransactionTestCase` race test |

---

## Findings

### 1. 🟡 Malformed / non-finite quantities → unhandled 500 instead of 400

**Files:** `inventory/services.py` (`_validate_received_qty` L80–84, `receive_goods` L134–135, `adjust_stock` L212–213), `inventory/console_views.py` (`except (ValidationError, ObjectDoesNotExist, ValueError, TypeError)` at L153 and L216).

Quantities are parsed with a bare `Decimal(str(value))` and guarded only with a `<= 0` / `== 0` comparison. Several malformed inputs fall through to an uncaught exception:

- `quantity_received: "abc"` → `Decimal("abc")` raises `decimal.InvalidOperation`, which is **not** a subclass of `ValueError` (it is an `ArithmeticError`), so it is **not** caught by the console view's `except` tuple → 500.
- `quantity_received: "NaN"` → `Decimal("NaN")` parses, then `qty <= 0` **raises** `InvalidOperation` (verified: `Decimal("NaN") <= 0` raises, unlike `== 0` which returns `False`) → 500.
- `adjust_stock` with `"NaN"`/`"Infinity"` → `Decimal("NaN") == 0` is `False` and `Decimal("Infinity") == 0` is `False`, so both pass the zero check; `_write_movement` then computes `item.quantity + NaN/Infinity` and `item.save()` → PostgreSQL `numeric` rejects it → `DataError` → 500.
- A line entry missing `quantity_received` → `entry["quantity_received"]` raises `KeyError` (not caught) → 500.
- A non-dict entry in `lines` (e.g. `["abc"]`) → `entry.get(...)` raises `AttributeError` (not caught) → 500.

The `adjust_stock` endpoint is partially shielded because the view pre-parses via `_parse_decimal` (which catches `InvalidOperation`), but that helper still returns `NaN`/`Infinity` as valid Decimals and does not check finiteness. The `receive` endpoint passes raw line dicts straight to `receive_goods`, so it is fully exposed.

**Suggested fix:** add a shared `_parse_quantity(value)` helper that wraps `Decimal(str(value))` in `try/except (InvalidOperation, TypeError, ValueError)` **and** rejects non-finite values (`not qty.is_finite()`), raises a `ValidationError` on failure. Use it in both `_validate_received_qty` and `adjust_stock`, and also catch `KeyError`/`TypeError`/`AttributeError` when normalising line entries (e.g. validate each `entry` is a `dict` and has a `quantity_received` key). Add `decimal.DecimalException` (or `ArithmeticError`) to the console view's `except` tuple as a final backstop.

---

### 2. 🟡 Duplicate `line_id`s in a receipt → `IntegrityError` → 500

**Files:** `inventory/services.py` (`receive_goods` validation loop L133–150, create loop L158–166).

The over-receipt check is computed per entry against the **committed** `GoodsReceiptLine` rows only (`_received_qty`), before any rows are created in the loop. Two entries for the *same* `line_id` both see the same `remaining` and both pass, e.g. `[{"line_id": 1, "qty": "6"}, {"line_id": 1, "qty": "6"}]` with remaining `10`. The create loop then inserts two `GoodsReceiptLine` rows for the same `(goods_receipt, purchase_order_line)`, which trips the `unique_goods_receipt_line` constraint → `IntegrityError` → not caught by the view → 500.

The unique constraint is a **good backstop** — without it this would silently over-receive (6 + 6 > 10) — but the failure surfaces as a 500 rather than a clean 400, and the validation never detects the aggregate over-receipt for the incoming batch itself.

**Suggested fix:** during normalisation, detect duplicate `line_id`s (e.g. a `seen` set, or accumulate requested quantity per line) and reject with a `ValidationError` before creating anything; optionally re-verify the *summed* requested quantity against `remaining` per line.

---

### 3. 🟢 `adjust_stock` returns the item, so the API's `quantity` is the balance, not the delta

**Files:** `inventory/services.py` (`_write_movement` L102–119 returns `item`; `adjust_stock` L216–224 returns it), `inventory/console_views.py` (`manage_stock_adjustment` L222).

`_write_movement` returns the updated `Item`, so `adjust_stock` returns the `Item` too. The view then responds with `{"item_id": updated.id, "quantity": str(updated.quantity)}` — i.e. the **post-adjustment total balance**, not the adjustment amount. The test `test_admin_can_adjust_stock` only passes because the item starts at `0` (`0 + 5 = 5`), masking the semantics. The current frontend ignores the response body, so there is no visible bug today, but the API contract is misleading and will bite any consumer (or future feature) that reads `quantity` as the delta.

**Suggested fix:** return the `StockMovement` from `_write_movement`/`adjust_stock`, and respond with the movement (adjustment delta) — or clearly separate fields, e.g. `{"item_id": ..., "quantity": <delta>, "balance": <new total>}`.

---

### 4. 🟢 Receipt stock movements aren't traceable back to their `GoodsReceipt` in the UI

**Files:** `inventory/console_views.py` (`_serialize_movement` L66–78), `inventory/models.py` (`StockMovement.content_object`).

`StockMovement` correctly stores a `GenericForeignKey` (`content_type`/`object_id`) pointing at the `GoodsReceipt` for receipt movements, but `_serialize_movement` does **not** surface `object_id`/`content_type`, and the movements table has no "reference" column. A receipt movement renders as `Item — Receipt — +10 — (no reason) — user — date` with no way to know *which* GR it came from. Given the ledger exists precisely for traceability, this is a real gap in the console.

**Suggested fix:** include `content_type`/`object_id` (or a resolved `receipt_id`/`reference`) in `_serialize_movement`, and render a "GR #" / reference column in the movements table.

---

### 5. 🟢 `get_receipt_summary` issues one aggregate query per line (N+1)

**File:** `inventory/services.py` (`get_receipt_summary` L235–251 calls `_received_qty` per line; `_received_qty` L69–73 runs a `Sum` aggregate each time).

For a PO with N lines, the summary performs N `Sum("quantity_received")` aggregate queries (plus the line fetch). Harmless at the stated ~500-user scale, but it's the kind of N+1 the codebase otherwise avoids via `select_related`/`prefetch_related`.

**Suggested fix:** fetch all received quantities in one grouped query, e.g. `GoodsReceiptLine.objects.filter(purchase_order_line__purchase_order=po).values("purchase_order_line_id").annotate(total=Sum("quantity_received"))`, then map line id → total.

---

### 6. 🟢 No `decimal_places`/`max_digits` validation on quantities

**Files:** `inventory/services.py` (`_validate_received_qty` L80–84, `adjust_stock` L212–213).

Neither path quantises or bounds the input. A value like `"0.0001"` passes `qty > 0`, and PostgreSQL `numeric(12,3)` silently rounds it to `0.000` — producing a zero-quantity receipt line and a zero movement while the in-memory `qty` was `0.0001` (so `Item.quantity` is bumped by `0.0001` in Python but stored as the rounded total). Conversely, an oversized value that exceeds `max_digits=12` (e.g. a huge adjustment) reaches the DB and raises `DataError` → 500. The frontend uses `step="0.001"`, so only crafted requests hit this, but it's the same "edge-case input" class as previous phases' #1/#2 fixes.

**Suggested fix:** quantise to `Decimal("0.001")` (or `Decimal("0.01")` per the tolerance decision), reject if it rounds to zero or exceeds `max_digits`, and fold this into the same guarded parser as finding #1.

---

### 7. 🔵 `StockMovement` GenericForeignKey has no DB-level "both-or-neither" guarantee

**File:** `inventory/models.py` (`StockMovement` L68–79).

`content_type` and `object_id` are independently nullable with no check constraint, so the DB cannot enforce that a polymorphic reference is either fully set or fully absent. In practice only `_write_movement` sets them and always sets both-or-neither, so there is no real risk today — but a future writer (or a superuser with shell access) could produce a dangling half-reference.

**Suggested fix:** add a `CheckConstraint` (`Q(content_type__isnull=True, object_id__isnull=True) | Q(content_type__isnull=False, object_id__isnull=False)`) and/or a `positive_int` guard; document that `object_id` is `PositiveIntegerField` so referenced models must use integer PKs (all current models do).

---

### 8. 🔵 Orphaned `actionReceive` i18n keys

**File:** `procurement/static/procurement/js/purchase_orders_i18n.js` (en L74, pt-PT L178).

The old `actionReceive` keys remain in both dictionaries but are no longer referenced — `purchase_orders.js` now uses `actionReceiveGoods` (L389). Harmless dead keys.

**Suggested fix:** remove the two `actionReceive` entries.

---

### 9. 🔵 No concurrency/race-coverage test

**File:** `inventory/tests.py`.

The locking logic is correct (verified by reading: PO locked first via `select_for_update()` in `receive_goods`, item locked in `_write_movement`, both under `@transaction.atomic`), but nothing exercises concurrent receipts/adjustments. As noted in prior reviews, the Django test client is single-threaded and CSRF-off, so concurrency and rollback are untested here.

**Suggested fix:** add a `TransactionTestCase` (or thread-based) test asserting two concurrent receipts for the same PO cannot over-receive, and/or a unit test asserting `select_for_update()` is issued (e.g. `assertNumQueries` / `CaptureQueriesContext` on the locked query).

---

## Verified-correct (checked, no issue)

- **Status machine** — `receive_goods` accepts only `APPROVED`/`RECEIVED`, rejects `draft`/`submitted`/`rejected`/`closed` with `PurchaseOrderNotReceivableError`; drives `approved → received` (via `procurement.services.receive`) and `→ closed` (via `close`) when fully received; partial receipts leave the PO `RECEIVED`; single-entry over-receipt is rejected (`InvalidReceivedQuantityError`) with rollback (all tested in `GoodsReceiptServiceTests`).
- **Concurrency** — `select_for_update()` on the PO (first) and the Item (in `_write_movement`), both wrapped in `@transaction.atomic`; nested `receive`/`close` calls are atomic and re-entrant; the aggregate `_received_qty` runs *after* the PO lock is acquired, so concurrent receipts for the same PO are correctly serialised and cannot over-receive.
- **Cached balance integrity** — `Item.quantity` is written **only** in `_write_movement` (never typed on the product): it's absent from `products/services.ITEM_UPDATABLE_FIELDS` and absent from `console.js` `formPayload()`, and read-only in `ItemAdmin` (`readonly_fields`). Movement insert + balance update happen in the same transaction, so they can't diverge.
- **Append-only ledger** — `PROTECT` on `GoodsReceipt.purchase_order`, `GoodsReceiptLine.purchase_order_line`, `StockMovement.item`/`content_type`; `SET_NULL` on `StockMovement.created_by`; `GoodsReceipt`/`StockMovement` admin is fully read-only (`has_add/change/delete` → `False`, superuser-only module).
- **Permissions** — `accounts/groups.py` grants `view/add/change/delete_goodsreceipt` per role (operators view-only, managers view+add+change, admins +delete), `view_goodsreceiptline`/`view_stockmovement` to all, and `can_adjust_stock` to admins only; `inventory_required` + `deny_unless` give defence-in-depth; operator-receipt / manager-adjust denials are tested (403).
- **API serialisation** — Decimals are serialised as strings everywhere (receipts, movements, summary), consistent with the existing consoles; no float leakage.
- **XSS** — zero `innerHTML` (grep-verified); all DOM rendered via `textContent`/`createElement`; `{{ user.email }}` is auto-escaped.
- **CSRF** — `X-CSRFToken` header sent from the meta tag; no `csrf_exempt` anywhere; views protected by middleware.
- **Double-submit** — `state.busy` guard + confirm-button disable in both `submitReceipt` and `submitAdjustment`, reset in `finally` (same pattern as the products console).
- **i18n** — en + pt-PT dictionaries complete for the new console, including the backend error codes (`purchase_order_not_receivable`, `invalid_received_quantity`, etc.), and `movement_type.*` labels.
- **Receipt-dialog reset + close confirmation** — `openReceiptDialog` re-populates the PO select and clears reference/notes/lines on each open; `close` now has a `window.confirm` prompt (`confirmClose`); the stale no-stock `receive/` endpoint and its UI are fully removed (no dangling references).
- **Migrations** — correct dependencies (`products.0005_item_quantity`, `procurement.0003_alter_purchaseorderchangelog_action`); `Item.quantity` is additive with `default=0` (no data-loss); the `GOODS_RECEIVED` action is a non-destructive `AlterField` with a superset of choices.

---

## Recommended priority

> *(Historical — this priority list was fully implemented in the Phase 3 follow-up. See §Fix status above.)*

1. **Fix #1 and #2** (malformed/non-finite/duplicate quantities → 500) — the one real robustness gap; cheap to fix with a shared guarded `Decimal` parser + duplicate-line detection, and it keeps the API's error contract honest (400 not 500).
2. **Fix #3** (adjust endpoint returns balance, not delta) — clarify the response contract before any consumer depends on it.
3. **#4, #6** — surface the receipt reference on movements (ledger traceability) and bound/quantise quantities.
4. **#5, #7, #8** — minor hardening/dead-code: single grouped aggregate, a GFK check constraint, and removing orphaned i18n keys.
5. **#9** — add a concurrency test when convenient (the locking logic is already correct).
