# CentCompras — Full-Codebase Deep Review (read-only)

> **Status: CLOSED — all N1–N12 findings applied (21 Aug 2026).** Archived; see [`handoff.md`](../handoff.md) for the current state. Do not treat as a work queue.

> **Read-only review.** No product code was changed for this document. Two independent passes (21 Aug 2026 morning) were merged, then re-checked against the tree **after** the 2208 remediation (P0–P4). Anything already closed in [`docs/archive/code-review-full-2026-08-20-2208.md`](code-review-full-2026-08-20-2208.md) is **not** repeated.

- **Date:** 21 August 2026, 13:03 WEST
- **Scope:** Phases 0–4 — `accounts`, `products`, `procurement`, `inventory`, `config`, `logging_utils` (working tree on `p4-m1-l-fixes`, including uncommitted P4)
- **Prior review:** 2208 — **concluded and archived.** H1–H3, M1–M6, M8–M10, L1–L12, L14 applied. M7 (pagination) and L13 (login rate limiting) remain deferred there; they are not re-opened here.

---

## Summary

The 2208 backlog is genuinely done. Locking, inactive-user sessions, D12 re-check, unique PO lines, one-primary supplier, sorted receipt locks, grades/approval limits, non-negative prices, and the L-series cleanups all hold in current code.

What remains is a **small net-new set** that 2208 never listed, plus a few **residuals of M2/M9** where the service layer was closed but admin, reactivate, pickers, or sibling consoles were not.

No critical defect under normal single-user console use. The items most likely to bite are: an approved PO that can never be cancelled (N1), banker's rounding on frozen approved totals (N7), and a handful of 500s / wrong-entity IDs on non-UI payloads.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| N1 | High | Procurement FSM | Approved PO with zero receipts cannot be cancelled or closed |
| N7 | Medium | Money | PO money `quantize()` uses banker's rounding (`ROUND_HALF_EVEN`) |
| N3 | Medium | PO console | New-PO / line pickers still list inactive suppliers and items |
| N5 | Medium | Products + PO | `reactivate_item` ignores inactive family; catalog and PO disagree |
| N8 | Medium | Admin | `InactiveFamilyError` escapes `ItemAdmin.save_model` → 500 |
| N9 | Medium | Procurement | Line totals can overflow `approved_*` `(14, 2)` → approve 500, PO stuck submitted |
| N12 | Medium | API | `_parse_int_id` never extended to products / inventory consoles |
| N4 | Low | Procurement | `update_line` still skips `full_clean` (extra decimal places round in PG) |
| N10 | Low | Products | Any `SupplierItemPrice` `IntegrityError` reported as duplicate price |
| N11 | Low | Inventory | Received qty silently quantizes to 3 dp (same rounding convention as N7) |

**Not in this list (already done or deferred in 2208):** H1–H3, M1–M6, M8–M10, L1–L14, M7, L13.

---

## High findings

### N1 — Approved PO with no receipts is stuck

**Files:** `procurement/services.py` — `STATUS_TRANSITIONS`, `receive_goods` (inventory), `close()`

```python
PurchaseOrder.Status.APPROVED: {PurchaseOrder.Status.RECEIVED},
PurchaseOrder.Status.RECEIVED: {PurchaseOrder.Status.CLOSED},
```

`receive_goods` requires `quantity_received > 0`. Manual `close()` only accepts `received`. There is no cancel / void / reject-after-approve.

**Scenario:** PO is approved; supplier never ships. Staff cannot close it without posting a token receipt, which writes stock.

**Impact:** Operational deadlock on a path that will happen. Workaround corrupts the ledger.

**Suggested fix:** `approved → cancelled` (or equivalent) when received qty is zero, with a required reason and changelog. Do not allow cancel once any receipt exists (use existing short-shipment `close()`).

**Status:** ✅ Done — added `PurchaseOrder.Status.CANCELLED` (migration `procurement/0006`), `services.cancel()` (reason required; rejects POs with any receipt), console endpoint `manage_purchase_order_cancel` (`CHANGE_PO`), frontend cancel action + status pill/filter + i18n (EN/pt-PT), and 6 tests.

---

## Medium findings

### N7 — Approved totals use banker's rounding

**Files:** `procurement/models.py` — `PurchaseOrderLine.net_unit_cost`, `line_net`, `line_vat`

Every `.quantize()` uses the ambient decimal context (`ROUND_HALF_EVEN`). There is no `ROUND_HALF_UP` / `localcontext()` in the tree.

**Scenario:** `unit_cost = 1.005`, qty 1, no discounts → `line_net` becomes `1.00` (0 is even). Commercial / PT invoicing typically rounds half away from zero to `1.01`. `approve()` freezes this into `approved_net` / `approved_vat` / `approved_gross`.

**Impact:** D13 snapshot can disagree with the supplier invoice by cents, with no way to explain the difference. Systematic on any half-even boundary.

**Suggested fix:** One explicit quantizer (`ROUND_HALF_UP` at 4 dp then 2 dp) used by `PurchaseOrderLine` (and later by orders). State the convention in handoff.

**Status:** ✅ Done — added `round_money()` (`ROUND_HALF_UP`) with `MONEY_4DP` / `MONEY_2DP` in `procurement/models.py`; applied to `net_unit_cost` (4 dp) → `line_net` / `line_vat` (2 dp). Convention documented as D28 in handoff. 3 tests.

---

### N3 — PO console offers inactive suppliers and items (M2 residual)

**Files:** `procurement/static/procurement/js/purchase_orders.js` — `fillSupplierSelect`, `fillItemSelect`; `products/console_views.py` — `get_items(active_only=False)`, `get_suppliers(active_only=False)`

M2 correctly rejects inactive supplier/item in `create_purchase_order` / `add_line`. The pickers still load the item-console payloads (which must include inactives) and do not filter `is_active`.

**Impact:** Staff pick a delisted row and get a 400. Dead-end UX introduced by the M2 server hardening.

**Suggested fix:** Filter the PO dropdowns to `is_active === true` (and skip items whose family is inactive if that flag is present). Do not change the item-console API.

**Status:** ✅ Done — `fillSupplierSelect` / `fillItemSelect` filter to `is_active === true` (items also require `family.is_active`).

---

### N5 — `reactivate_item` bypasses the family-active rule (M2 residual)

**Files:** `products/services.py` — `reactivate_item`, `bulk_reactivate_items`, `get_catalog`; `procurement/services.py` — `_ensure_item_active`

`_ensure_family_active` guards `create_item` / `update_item`, not `reactivate_item`. An item under an inactive family can be set `is_active=True`. Then:

- `get_catalog()` hides it (`family__is_active=True`)
- `add_line` / `submit` / `approve` accept it (`Item.is_active` only)
- `receive_goods` never checks activity

D16 still stands: do **not** cascade-deactivate items when a family is deactivated. This finding is the other door: do not **reactivate** (or PO) an item whose family is inactive.

**Bite-risk:** Seed historically created this shape (Legacy family). One reactivate click away.

**Suggested fix:** `_ensure_family_active(item.family)` in `reactivate_item`. Optionally also reject `add_line` when `family.is_active` is false.

**Status:** ✅ Done — `reactivate_item` calls `_ensure_family_active`; procurement `_ensure_item_active` now also requires `family__is_active`, so add/submit/approve reject items under an inactive family (closes the D16 non-cascade door).

---

### N8 — `InactiveFamilyError` from admin is a 500 (M2 regression)

**Files:** `products/admin.py` — `ItemAdmin.save_model`; `products/services.py` — `_ensure_family_active`

`save_model` catches only `DuplicateInternalCodeError`. Family autocomplete is not limited to active families. Superuser picks seeded Legacy → `create_item` / `update_item` raises `InactiveFamilyError` → unhandled 500.

**Suggested fix:** Catch `InactiveFamilyError` (and map to `{"family": ...}`). Filter autocomplete to active families.

**Status:** ✅ Done — `ItemAdminForm.clean_family` rejects inactive families (form error instead of a 500; note a `save_model` `ValidationError` would not attach to the form). `FamilyProductAdmin.get_search_results` filters the family autocomplete to active families; bulk-reactivate (admin + console) handles `InactiveFamilyError` gracefully.

---

### N9 — Approve snapshot can overflow `approved_*`

**Files:** `procurement/services.py` — `approve`; `procurement/models.py` — `approved_net/vat/gross` `(14, 2)`; `_status_action` catches `ValidationError` only

L7 capped **line quantity** at `< 1e9`. `unit_cost` is still `(12, 2)`. Individually valid lines can total past `999,999,999,999.99`. `po.save()` raises `DataError`; the request 500s; the PO stays `submitted`.

**Suggested fix:** After `po.totals()`, reject if any of net/vat/gross has `copy_abs() >= 1e12` (or raise `ValidationError` before save). Same cap on `_validate_unit_cost` if product wants a tighter bound.

**Status:** ✅ Done — `approve()` raises `ApprovalTotalOverflowError` (caught by `_status_action` → 400) when any of net/vat/gross is `>= 1e12` (the `(14,2)` limit), before `po.save()`. Added `MAX_APPROVED_TOTAL`. Unit-cost bound left as-is (the approve-time guard fully prevents the 500).

---

### N12 — Strict int IDs were applied to procurement only (M9 leftover)

**Files:** `products/console_views.py` — `int(family_id)`, `int(vat_rate_id)`, `int(supplier_id)`, `int(item_id)`, bulk `[int(item) for item in ids]`; `inventory/console_views.py` — raw `purchase_order_id` / `item_id` / `line_id`

2208 M9 is done **for procurement** (`_parse_int_id` rejects floats/bools). Sibling consoles still use `int()`, so `true` → 1 and `1.9` → 1.

**Scenario:** `POST /api/manage/stock-adjustments/` with `{"item_id": true, "quantity": "-5", "reason": "…"}` adjusts item 1, HTTP 200, misleading ledger row. Bounded: JS sends `Number(select.value)`; needs a non-UI client with write permission. Adjust-stock is the destructive case.

**Suggested fix:** Reuse `_parse_int_id` (or one shared parser) on products + inventory mutating IDs. Catch `OperationalError` on receive is **not** required now that M6 sorts locks — do not treat that as a separate item.

**Status:** ✅ Done — copied `_parse_int_id` into `products/console_views.py` and `inventory/console_views.py` (matching the codebase's per-app helper duplication) and applied to all mutating IDs: item create/update (`family_id`, `vat_rate_id`), bulk `ids`, supplier-item-price create (`supplier_id`, `item_id`), goods-receipt (`purchase_order_id`, `line_id`), and stock adjustment (`item_id`).

---

## Low findings

| ID | Finding | Suggested fix |
|----|---------|---------------|
| N4 | `add_line` calls `full_clean`; `update_line` does not. Extra decimal places round in PostgreSQL. Quantity overflow is largely closed by L7. | Quantize in `_validate_quantity` / `_validate_unit_cost`, or `full_clean` on update. |
| N10 | `_save_supplier_item_price` maps **every** `IntegrityError` to “duplicate supplier price”, including the primary-unique constraint. | Inspect constraint name; H3 locking itself holds. |
| N11 | `_parse_decimal_quantity` quantizes to 3 dp with banker's rounding before the over-receive check; `10.0005` stored as `10.000` with no warning. | Same convention as N7; reject or round-half-up explicitly. |

---

## Already closed (do not re-implement)

See 2208 tracker. Confirmed still holding in this tree:

| ID | Evidence |
|----|----------|
| H1 | `_lock_po()` on add/update/remove line; PO locked before line |
| H2 | `deny_if_inactive` on all three `*_required` gates |
| H3 | partial unique primary + item lock |
| M1 | `_validate_non_negative` + `MinValueValidator` + `CheckConstraint`s |
| M2 | inactive supplier/item blocked on create/add/submit/approve; catalog excludes inactive families (**residuals: N3, N5, N8**) |
| M3 | D12 re-check on submit and approve |
| M4 | `unique_po_line_item` + `DuplicatePOLineError` |
| M5 | `item_quantity_gte_zero`; `ledger_quantity()` |
| M6 | `receive_goods` locks items `order_by("pk").select_for_update()` |
| M8 | exclusive `assign_warehouse_group`; code-owned `permissions.set()` |
| M9 | procurement `_parse_int_id` + stock balance cap (**leftover: N12**) |
| M10 | grades, `ApprovalLimit`, required reasons, `transaction.on_commit` stub |
| L1–L12, L14 | applied (L6 finite parse is products + procurement; inventory view parser still defers to the service) |
| M7 | ⏸ Deferred (scale) — consoles assume full lists |
| L13 | ⏸ Deferred — pre-production login rate limit |

---

## What looks solid

Mutations through `services.py`. CSRF on; no `innerHTML`. Superuser admin cannot edit quantity, POs, receipts, or movements. Same-PO over-receive locked and tested. D13 snapshot under PO row lock. No Item-before-PO lock inversion after H1. Negative stock blocked. Unique PO line and unique primary are DB-backed.

---

## Enhancement proposals (only what still meets the bar)

1. **Cancel/void approved POs with zero receipts** — that is N1, not a separate product idea.
2. **One money-rounding module** (`ROUND_HALF_UP` at 4 dp / 2 dp) used by `PurchaseOrderLine` now and by orders later — that is N7. Do not leave rounding as “whatever the decimal context is”.

A shared request-parser is **how you finish N12**, not a third enhancement. Pagination (M7), email product (Phase 6), branches, and opening-balance `INITIAL` stay out.

---

## Suggested remediation priority

| Priority | Items | Rationale |
|----------|-------|-----------|
| **P0** | N1 | Operational deadlock; no workaround that does not write fake stock |
| **P1** | N7, N5, N8, N3 | Invoice cents; M2 residuals staff will hit |
| **P2** | N12, N9 | Wrong-entity IDs; approve 500 |
| **P3** | N4, N10, N11 | Cleanup when touching related code |

---

## Fix status tracker

| ID | Status |
|----|--------|
| N1 | ✅ Done |
| N7 | ✅ Done |
| N3 | ✅ Done |
| N5 | ✅ Done |
| N8 | ✅ Done |
| N9 | ✅ Done |
| N12 | ✅ Done |
| N4 | ✅ Done |
| N10 | ✅ Done |
| N11 | ✅ Done |
| M7 / L13 | ⏸ Already deferred in 2208 — not this backlog |

---

## Comparison with 2208

2208 closed concurrency (H1/H3/M6), auth (H2), D12 (M3), duplicates (M4), lifecycle create/submit (M2), prices (M1), audit/SoD (M10), and L1–L14. **This document is only the leftover and net-new surface** — FSM cancel, rounding convention, M2/M9 residuals, and approve overflow.
