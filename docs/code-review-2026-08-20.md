# CentCompras — Code Review (Phase 2 + cross-cutting)

> Read-only review. Scope: whole project, prioritising Phase 1 pricing + Phase 2 procurement and recent cross-cutting changes (timezone, date format, primary-demotion audit). No code changed during this review.

- **Date:** 20 August 2026
- **Test baseline:** `products accounts procurement` → **148 tests, OK** (`node --check` clean on both JS bundles; zero `innerHTML`).

---

## Summary

No **critical** (data-loss/corruption) defects remain — the discount-total bug found during UI testing was the main one and is already fixed with regression tests. The findings below are **medium/low severity** plus two "info" items to settle before Phase 3. The single most worth-fixing item is **#1**, because it's the same class of "edge case getting through" the user has been hitting.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| 1 | 🟡 Medium | Frontend | Clearing an optional numeric field → empty string → HTTP 400 with a cryptic "must be a number" error |
| 2 | 🟢 Low | Frontend | Backend error messages are not localised (show English even in pt-PT) |
| 3 | 🟢 Low | Backend | `net_unit_cost` is not rounded → inconsistent decimal display |
| 4 | 🟢 Low | Backend | Changing a PO's supplier (service) does not re-price existing lines |
| 5 | 🟢 Low | Frontend | `formatCost`/`formatPercent` use `Number()` → precision loss on large values |
| 6 | 🟢 Low | Backend | Zero-cost lines are created silently when an item has no supplier price |
| 7 | 🔵 Info | Backend | `rejected` is terminal — no "reopen to draft" transition |
| 8 | 🔵 Info | Backend | `receive` does not write stock (Phase 3) but is already reachable in the UI |

---

## Findings

### 1. 🟡 Empty optional numeric field → HTTP 400

**Files:** `products/static/products/js/console.js` (`formPayload`, `submitSupplierPriceAdd`), `procurement/static/procurement/js/purchase_orders.js` (`onLineConfirm`).

Three places send the raw `<input>.value` for an *optional* numeric field. If a user selects the value and clears it (a natural way to mean "0"/"none"), the field value is `""`, which is sent to the API and rejected server-side with "… must be a number."

- Item selling prices (`retail_price` / `wholesale_price` / `special_price`) in `formPayload()` — inputs have no `required`.
- Supplier cost price in `submitSupplierPriceAdd()` (`cost_price`).
- PO line discounts (`discount_commercial` / `discount_financial` / `rappel`) in `onLineConfirm()`.

**Suggested fix:** coerce empty → `"0"` before building the payload (or omit the key and let the server default), e.g. a small `numOrZero(input.value)` helper. Backend already defaults discounts to 0 and selling prices to 0 when omitted, so omitting empty is the cleanest.

### 2. 🟢 Error messages not localised

**File:** `procurement/static/procurement/js/purchase_orders.js` (`api()`), both i18n files.

The `api()` helper maps `payload.code` through `t()`, but the backend error codes (`invalid_quantity`, `invalid_unit_cost`, `invalid_discount`, `invalid_total_discount`, `invalid_status_transition`, `empty_purchase_order`, `purchase_order_not_draft`) have no i18n keys, so it falls back to the English `payload.error`. A pt-PT user sees English errors.

**Suggested fix:** add these code keys to both `en` and `pt-PT` dicts in `purchase_orders_i18n.js` (and products `console_i18n.js` for the pricing codes).

### 3. 🟢 `net_unit_cost` precision inconsistent

**File:** `procurement/models.py` (`PurchaseOrderLine.net_unit_cost`).

`line_net` / `line_vat` / `line_total` are `.quantize(Decimal("0.01"))`, but `net_unit_cost` is not, so `unit_cost × (1 − d%)` can show e.g. `2.51342` next to `2.60` and `25.13`. Not a correctness bug (Decimal math is exact), purely display.

**Suggested fix:** `quantize(Decimal("0.0001"))` (or `0.01`) in `net_unit_cost`.

### 4. 🟢 Supplier change does not re-price lines

**File:** `procurement/services.py` (`update_purchase_order` allows `supplier`; lines keep their old auto-filled `unit_cost`).

`PO_UPDATABLE_FIELDS` includes `"supplier"`, so a draft PO can be moved to another supplier while its lines still carry costs auto-filled from the *old* supplier's price list. Not reachable through the current API (only `supplier_ref`/`notes` are exposed), but it's a latent inconsistency if supplier-editing is ever surfaced.

**Suggested fix:** remove `"supplier"` from `PO_UPDATABLE_FIELDS` (make supplier immutable after creation), or re-run `_default_unit_cost` for each line when supplier changes.

### 5. 🟢 `Number()` used for currency/percent formatting

**File:** `procurement/static/procurement/js/purchase_orders.js` (`formatCost`, `formatPercent`).

`Number(value).toFixed(2)` converts a decimal string to a JS float, losing precision for values beyond ~15 significant digits (large PO totals). At current scale this is harmless, but it's the wrong tool for money.

**Suggested fix:** format the string directly (split on `.`, pad/round) instead of going through `Number`.

### 6. 🟢 Zero-cost lines created silently

**File:** `procurement/services.py` (`_default_unit_cost` returns `Decimal("0")` when an item has no supplier price; `add_line` accepts it).

If an item has no `SupplierItemPrice`, a line is auto-filled with cost `0` with no warning — easy to miss and submit. Not corruption, but a silent default.

**Suggested fix:** surface a hint in the UI ("no supplier price — cost set to 0"), or require an explicit `unit_cost` when no price exists.

### 7. 🔵 `rejected` is terminal

**File:** `procurement/services.py` (`STATUS_TRANSITIONS`).

There is no transition out of `rejected`. A PO rejected by mistake cannot be reopened as a draft. Likely a desired feature later.

### 8. 🔵 `receive` does not write stock (Phase 3), but is reachable now

**File:** `procurement/services.py` (`receive` is a status-only transition; stock writing is Phase 3).

Managers/admins can already click **Receive** in the console, which marks a PO "received" *without* creating any stock movement. This is correct per the plan (goods receipt is Phase 3), but worth a deliberate decision: either hide the **Receive** button until Phase 3, or document it as "confirmation only, no stock yet."

---

## Verified-correct (checked, no issue)

- **Permission gating** is solid: backend `deny_unless` + service checks, frontend CSS hides `#new-po` for read-only users, and every mutation re-checks `poPermissions()`/`catalogPermissions()` (defence-in-depth).
- **Discount validation** now enforces both per-field 0–100 *and* combined ≤ 100 (the fixed bug), with regression tests for `add_line` and `update_line`.
- **Status machine** rejects out-of-order transitions (e.g. draft→approved) via `InvalidStatusTransitionError`.
- **Auto-cost** prefers the PO's supplier price, falls back to primary then cheapest, and is always overridable (D11).
- **Audit logging** is complete for PO create/update/line-add/update/remove/status changes, and the primary-demotion now writes an audit entry too.
- **Timezone** activates per-user (default `Europe/Lisbon`), falls back to UTC on invalid, and dates render DD/MM/YYYY 24h client-side.
- **`node --check`** passes; **zero `innerHTML`**; 148 Django tests green.

---

## Recommended priority

1. **Fix #1** (empty numeric field → 400) — the one real papercut users will hit.
2. **#2, #3** — cheap polish (localise errors, round `net_unit_cost`).
3. **#4, #6** — small backend hardening before Phase 3.
4. **#7, #8** — decide during Phase 3 planning (reopen; receive vs. stock).
