# CentCompras — Full-Codebase Deep Review (read-only)

> **Status: OPEN — findings not yet applied.** When all actionable items are fixed (or explicitly deferred with rationale), move this file to `docs/archive/` and update [`handoff.md`](handoff.md). Archived reviews are concluded backlogs, not live work queues.

> **Read-only review.** No code was changed during this review. This document is the live backlog until remediated.

- **Date:** 20 August 2026, 22:08 WEST
- **Scope:** Phases 0–4 — `accounts`, `products`, `procurement`, `inventory`, `config`, `logging_utils`
- **Prior review:** [`docs/archive/code-review-full-2026-08-20-1928.md`](archive/code-review-full-2026-08-20-1928.md) — concluded; all 14 findings resolved or deferred. This review adds **net-new** findings on top of that hardened baseline.

---

## Summary

The architecture remains sound: mutations through `services.py`, `@transaction.atomic` + `select_for_update()` on status transitions, stock ledger append-only with `Item.quantity` written only in `_write_movement`, audit-by-design, superuser-only admin, CSRF enforced, plain JS without `innerHTML`.

**No critical defect** under normal single-user operation. The findings most likely to bite in production or under concurrent use cluster in three areas:

1. **Concurrency gaps** — PO line mutations and primary-supplier updates lack the same locking discipline as submit/approve/receive.
2. **Lifecycle validation holes** — inactive users, inactive catalogue entities, and deleted supplier prices are not consistently enforced at the right boundaries.
3. **Defence-in-depth gaps** — ledger/cache consistency and several invariants exist only in Python, not in the database.

| # | Severity | Area | Summary |
|---|----------|------|---------|
| H1 | High | Procurement | PO line mutations race with submit/approve (breaks D13 snapshot) |
| H2 | High | Auth | Deactivated users retain console/API access until session expires |
| H3 | High | Products | Concurrent primary supplier prices can leave multiple primaries |
| M1 | Medium | Products | Negative selling prices and reorder levels accepted |
| M2 | Medium | Cross-app | Active items under inactive families; inactive entities on POs |
| M3 | Medium | Procurement | Supplier price (D12) validated only at line-add, not at submit |
| M4 | Medium | Procurement | Duplicate PO lines for same item allowed |
| M5 | Medium | Inventory | `Item.quantity` cache not tied to ledger at DB level |
| M6 | Medium | Inventory | Multi-item receipt deadlock risk |
| M7 | Medium | Scale | Unpaginated list endpoints (console, catalog, PO, receipts, movements) |
| M8 | Medium | Accounts | Warehouse group permission sync/reassign footguns |
| M9 | Medium | API | Bad `item_id` → 500; int truncation; cumulative stock overflow |
| M10 | Medium | Audit | Self-approval, empty close/adjust reasons, email inside transaction |
| L1–L14 | Low | Various | See [Low findings](#low-findings) |

---

## High findings

### H1 — PO line mutations can race with submit/approve (breaks D13 snapshot)

**Files:** `procurement/services.py` — `add_line` (175–219), `update_line` (246–255), `remove_line` (297–299)

`submit()`, `approve()`, and other status changes lock the PO with `select_for_update()`. Line mutations do **not**:

```python
po = _resolve_po(po)
_ensure_draft(po)
# ... line saved without PO row lock
```

**Scenario:** Thread A calls `add_line` → passes `_ensure_draft`. Thread B submits/approves (locks PO, snapshots `approved_net`/`approved_vat`/`approved_gross`). Thread A saves a new line on an approved PO.

**Impact:**

- Violates “lines editable only in draft”
- **D13 integrity break:** approved financial snapshot frozen without the sneaked line; goods can still be received against it via inventory
- Same class of race on `update_line` / `remove_line` (line locked, PO not)

**Suggested fix:** Lock PO at start of all line mutators: `po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)` then `_ensure_draft(po)`. Add concurrent integration tests.

**Status:** ✅ Done — `_lock_po()` used by `add_line` / `update_line` / `remove_line`; FOR UPDATE tests added.

---

### H2 — Deactivated users retain full console/API access until session expires

**Files:** `products/permissions.py` (47–62), `procurement/permissions.py`, `inventory/permissions.py`

Decorators check `is_authenticated` only — not `is_active`. Django blocks new logins for inactive users but does not invalidate existing sessions. `/admin/` correctly requires `is_active` (`accounts/admin_site.py`).

**Impact:** Offboarded user retains read/write access until cookie expiry.

**Suggested fix:** Shared guard in all `*_required` decorators or middleware: if not `request.user.is_active` → 403 + optional logout. Add test: deactivate user mid-session → API returns 403.

**Status:** ✅ Done — `accounts/authz.py` (`deny_if_inactive` / `user_is_active`); wired into all three `*_required` decorators; session leftover for inactive users cleared with 403.

---

### H3 — Concurrent “primary” supplier prices can leave multiple primaries

**Files:** `products/services.py` — `_clear_other_primaries` (779–798), `create_supplier_item_price`, `update_supplier_item_price`

“One primary per item” is enforced in Python only. Two concurrent requests setting `primary=True` can each save before the other clears rivals. No partial unique DB index.

**Impact:** `catalog_buying_price()` uses `next(...)` on primaries — cost becomes **non-deterministic** if duplicates exist. PO costing and catalog can disagree.

**Suggested fix:** PostgreSQL partial unique index `UNIQUE (item_id) WHERE primary = TRUE`; lock `Item` row before primary mutations; reconciliation migration if needed.

**Status:** ✅ Done — partial unique constraint + migration `0006`; clear-then-save primary with item row lock; IntegrityError / FOR UPDATE tests added.

---

## Medium findings

### M1 — Negative selling prices and reorder levels accepted

**Files:** `products/services.py` — `create_item`, `update_item`

Cost prices reject negatives/NaN via `_validate_cost_price`, but `retail_price`, `wholesale_price`, `special_price`, and `reorder_level` have no equivalent checks.

**Impact:** Invalid catalogue data; `catalog_below_reorder()` misleading with negative reorder levels.

**Suggested fix:** Add non-negative validation in services; optionally `MinValueValidator(0)` on model fields.

**Status:** ⏳ Open

---

### M2 — Active items under inactive families; inactive entities on POs

**Files:** `products/services.py` — `get_catalog`; `procurement/services.py` — `create_purchase_order`, `add_line`, `submit`

Family deactivation does not affect items. PO creation/add/submit never checks `supplier.is_active` or `item.is_active`.

**Impact:** Orders and manager catalog can reference delisted/inactive catalogue entities.

**Suggested fix:** Decide explicit rules; enforce at create/add/submit boundaries; optionally exclude items whose family is inactive from `get_catalog`.

**Status:** ✅ Done — inactive supplier/item blocked on create/add/submit/approve; inactive family blocked on create/update item; `get_catalog` excludes inactive families; seed creates Legacy stock items then deactivates family.

---

### M3 — Supplier price (D12) validated only at line-add, not at submit

**Files:** `procurement/services.py` — `add_line` (191–195) vs `submit` (374–392)

If `SupplierItemPrice` is deleted while PO is draft/submitted, submit/approve proceed without re-check.

**Impact:** D12 (“reject if no price”) bypassed at approval time.

**Suggested fix:** `_validate_all_lines_have_supplier_price(po)` called from `submit()` (minimum).

**Status:** ✅ Done — price re-check on `submit()` and `approve()`; tests cover deleted `SupplierItemPrice`.

---

### M4 — Duplicate PO lines for same item allowed

**Files:** `procurement/models.py`, `procurement/services.py` — `add_line`

No `UniqueConstraint(purchase_order, item)` and no service check.

**Impact:** Same item twice on one PO — split quantities, confusing receipt UX.

**Suggested fix:** Enforce uniqueness or merge quantities; document chosen behaviour.

**Status:** ✅ Done — reject duplicates (`unique_po_line_item` + `DuplicatePOLineError`); no merge.

---

### M5 — `Item.quantity` cache not tied to ledger at DB level

**Files:** `inventory/services.py` — `_write_movement`; `products/models.py` — `Item.quantity`

Documented as cached sum of `StockMovement`, but nothing in DB prevents drift (shell, raw SQL, future code).

**Suggested fix:** Integrity check command/test; long-term `CheckConstraint(quantity >= 0)` after backfill.

**Status:** ⏳ Open

---

### M6 — Multi-item receipt deadlock risk

**Files:** `inventory/services.py` — `receive_goods` loop, `_write_movement`

Each line locks items in payload order. Two concurrent receipts touching overlapping items in different order can deadlock in PostgreSQL.

**Suggested fix:** Collect all affected item IDs; lock in sorted order before writing movements.

**Status:** ⏳ Open

---

### M7 — Unpaginated list endpoints

**Files:**

- `products/static/products/js/console.js` — `loadCatalog()` calls API without `page`/`page_size`
- `products/console_views.py` — `_console_payload` supports pagination but frontend does not use it
- Manager catalog, PO list, goods receipts, stock movements — no pagination

**Impact:** Memory/latency growth as data accumulates (same class as prior review #11, still deferred at small scale).

**Suggested fix:** Default paginated responses; wire console JS; add pagination to catalog/PO/receipt/movement APIs.

**Status:** ⏸ Deferred (scale) — track here until implemented

---

### M8 — Warehouse group permission management footguns

**Files:** `accounts/groups.py`

- `sync_warehouse_groups()` uses `group.permissions.set(desired)` — replaces entire permission sets on migrate; manual admin additions wiped.
- `assign_warehouse_group()` is additive — role reassignment without removing old group leaves elevated permissions.

**Suggested fix:** Merge instead of replace, or document code-only management; make role assignment exclusive.

**Status:** ⏳ Open

---

### M9 — API robustness gaps

| Issue | File | Impact |
|-------|------|--------|
| Bad `item_id` on add-line → 500 | `procurement/console_views.py` 222–241 | `Item.DoesNotExist` uncaught |
| `int(1.9)` silently truncates IDs | procurement console views | Wrong entity selected |
| Cumulative stock balance overflow | `inventory/services.py` `_write_movement` | `DataError` at save instead of clean 400 |

**Status:** ✅ Done — add-line catches missing item (404); `_parse_int_id` rejects floats; `_write_movement` rejects balance ≥ 1e9.

---

### M10 — Audit and control gaps (policy)

| Issue | Impact |
|-------|--------|
| Self-approval allowed | Weak segregation of duties |
| Manual PO `close()` has no server-side reason | Partial receipt write-offs not auditable |
| `adjust_stock` allows empty reason | Weak audit for admin-only operation |
| `PurchaseOrderChangeLog.reason` never populated | Status decisions lack “why” |
| `notify_supplier_on_approval` inside transaction | Phase 6 email could fire before commit rolls back |

**Suggested fix:** Policy decisions first, then implement reasons / self-approval rule / `transaction.on_commit()` for email.

**Status:** ⏳ Open (email part deferred to Phase 6)

---

## Low findings

| ID | Finding | Suggested fix |
|----|---------|---------------|
| L1 | Empty `description` allowed via admin/CLI but not console API | Validate in `create_item` |
| L2 | Family rename via PATCH API despite “console does not rename” policy | Remove from updatable fields or add UI |
| L3 | Inactive suppliers/items can still get new `SupplierItemPrice` rows | Reject at create |
| L4 | `VatRate.rate` has no range validation | CheckConstraint or service validation |
| L5 | PO line serializer omits `line_vat` | Add to `_serialize_line` |
| L6 | `procurement/console_views._parse_decimal` weaker than service parser | Share finite-aware parser |
| L7 | No upper bound on PO quantity | Business max or match inventory limits |
| L8 | `User.timezone` not validated at save; middleware no `finally: deactivate()` | Model clean + middleware fix |
| L9 | Dashboard lists all permission codenames | Hide outside DEBUG or for superusers only |
| L10 | Unused enum values (`INITIAL`, price DEACTIVATED/REACTIVATED) | Remove or implement |
| L11 | `CHANGE_GOODS_RECEIPT` permission defined but unused | Remove or implement edit flow |
| L12 | Production session/CSRF/TLS settings absent from `settings.example.py` | Commented production block in template |
| L13 | No login rate limiting | `django-axes` or proxy rate limit before prod |
| L14 | Test gaps: PO line concurrency, primary race, ledger sum == quantity | Add when fixing H1/H3/M5 |

---

## Cross-app flow (where H1 surfaces)

```text
SupplierItemPrice ──D12──► Draft PO lines ──H1 race──► Approve + snapshot
                                                              │
                                                              ▼
                                                    receive_goods ──► StockMovement ──► Item.quantity
```

H1 is the only path that can silently break the link between **approved totals** and **receivable lines**.

---

## What looks solid (no action needed)

| Area | Assessment |
|------|------------|
| PO status FSM | Coherent transitions; `reopen` limited correctly |
| Approved snapshot at `approve()` | Matches D13; tested |
| Single-line over-receive race | PO row lock + aggregate check; concurrent test exists |
| Negative stock on adjustment | Blocked in `_write_movement`; tested |
| CSRF | Middleware on; JS sends token; no `csrf_exempt` |
| XSS | Frontend uses `textContent`/`createElement` |
| Admin bypass | POs, receipts, movements read-only; superuser-only site |
| NaN/Infinity parsing | Fixed in procurement/products/inventory (prior review) |
| Permission tiers | Admins / managers / operators align with groups and tests |
| Duplicate line in one receipt payload | Rejected in service |

---

## Suggested remediation priority

| Priority | Items | Rationale |
|----------|-------|-----------|
| **P0** | H1, H2, H3 | Data integrity, auth, pricing determinism |
| **P1** | M3, M2, M4, M9 | Locked business rules (D12) and API hygiene |
| **P2** | M5, M6, M7, M8 | Scale, deadlock, drift, role management |
| **P3** | M10 | Segregation of duties, audit reasons, `on_commit` email |
| **P4** | L1–L14 | Cleanup when touching related code |

---

## Enhancement proposals (optional)

1. **Integrity command** — `reconcile_stock`: assert `Item.quantity == Sum(StockMovement.quantity)` per item.
2. **DB constraints** — partial unique on primary supplier; checks on quantity ≥ 0, receipt qty > 0.
3. **Pagination defaults** — wire item console JS; catalog, PO list, receipts, movements.
4. **Lifecycle middleware** — single active-user check + optional session invalidation on deactivation.
5. **Submit-time validation bundle** — price, active entities, duplicate lines at `submit()`.
6. **Audit reasons** — required on `reject()`, manual `close()`, `adjust_stock()`.
7. **Email Phase 6 prep** — `notify_supplier_on_approval` via `transaction.on_commit()`.
8. **Production settings block** — commented template for secure cookies, HSTS, trusted origins.
9. **Opening balance** — implement or remove `StockMovement.Type.INITIAL` until needed.
10. **Manager catalog** — exclude items under inactive families; consistent below-reorder rules.

---

## Fix status tracker

Update this table as work completes. Move the whole doc to `docs/archive/` when every ⏳ item is ✅ or ⏸ with documented rationale.

| ID | Status |
|----|--------|
| H1 | ✅ Done |
| H2 | ✅ Done |
| H3 | ✅ Done |
| M1 | ⏳ Open |
| M2 | ✅ Done |
| M3 | ✅ Done |
| M4 | ✅ Done |
| M5 | ⏳ Open |
| M6 | ⏳ Open |
| M7 | ⏸ Deferred (scale) |
| M8 | ⏳ Open |
| M9 | ✅ Done |
| M10 | ⏳ Open |
| L1–L14 | ⏳ Open |

---

## Comparison with prior review

[`docs/archive/code-review-full-2026-08-20-1928.md`](archive/code-review-full-2026-08-20-1928.md) fixed NaN→500, negative adjust stock, XSS, N+1, catalog filter race, etc. **This document is the new live backlog** — especially H1–H3 and cross-cutting M2–M4, which were not in the prior review.
