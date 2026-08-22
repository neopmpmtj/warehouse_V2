# CentCompras — Session Handoff

> **Read this first when resuming work.** Last updated: 21 August 2026, 22:01 WEST.

---

## TL;DR — where we are

| Phase | Status |
|-------|--------|
| 0 — Auth + catalogue identity + staff console | ✅ Done |
| 1 — Pricing (selling prices + supplier price list) | ✅ Done |
| 2 — Procurement (purchase orders) | ✅ Done |
| **3 — Goods receipt + stock ledger** | ✅ **Done** |
| **4 — Manager catalog (stock + price view)** | ✅ **Done** |
| 5 — Branches + internal request | ✅ **Done** |
| 6 — Email automation | 🔜 Next (stub exists) |
| 7 — Mobile / offline / PWA / OAuth | ⏸ Future |

**Phases 0–5 are complete.** Phase 5 decisions are **locked**; **Slices 1–6 are done** (tenancy, branch catalog, requisição interna, warehouse goods issue, branch receipt + branch stock, and polish). Phase 6 (email automation) is next. Phase 7 stays future.

**The 1303 review is complete and archived** ([`docs/archive/code-review-full-2026-08-21-1303.md`](archive/code-review-full-2026-08-21-1303.md)). All N1–N12 findings are fixed. **Phases 0–4 are stable; the full suite is green (378 tests).**

**Next task:** **Phase 6 — email automation** — wire the notify stubs to real email (SMTP/provider), templates EN + pt-PT. See [`docs/PROJECT-PLAN.md`](PROJECT-PLAN.md) §13. L13 (login rate limiting) stays deferred — production-only.

---

## Next session — do this

1. **Next task:** **Phase 6 — email automation** — wire the notify stubs (`notify_supplier_on_approval`, and the request/issue/receipt events) to real email. **Phase 5 is complete** (Slices 1–6: tenancy, catalog, requisição, goods issue, branch receipt + stock, polish). M7 (console pagination) is done.
2. **Review backlog is cleared** — all N1–N12 items in the 1303 review are fixed and the review is archived. Do **not** treat it as a work queue.
3. **Do not re-implement 2208** — H1–H3, M1–M6, M8–M10, L1–L12, L14 are done; L13 (login rate limiting) is the only one still open (production-only, deferred).
4. **Do not start** orders, offline, shared chrome, or Phase 6 email without a plan. If the test DB goes stale after a schema change, recreate it **without** `--keepdb`.

---

## Live review (1303 — concluded & archived)

Archived: [`docs/archive/code-review-full-2026-08-21-1303.md`](archive/code-review-full-2026-08-21-1303.md). Do not treat as a work queue.

| ID | Sev | Summary | Status |
|----|-----|---------|--------|
| N1 | High | Approved PO with zero receipts cannot be cancelled | ✅ Done |
| N7 | Medium | Banker's rounding on `approved_*` totals | ✅ Done |
| N3 | Medium | PO pickers list inactive suppliers/items | ✅ Done |
| N5 | Medium | `reactivate_item` ignores inactive family | ✅ Done |
| N8 | Medium | Admin `InactiveFamilyError` → 500 | ✅ Done |
| N9 | Medium | Approve overflow on `approved_*` (14,2) | ✅ Done |
| N12 | Medium | `_parse_int_id` not used in products/inventory | ✅ Done |
| N4 | Low | `update_line` skips `full_clean` | ✅ Done |
| N10 | Low | Price `IntegrityError` always reported as duplicate | ✅ Done |
| N11 | Low | Receipt qty silent 3 dp quantize | ✅ Done |

All N1–N12 findings applied. (M7 and L13 were 2208 items, outside this review's scope — M7 is now done; L13 remains deferred.)

---

## Review progress (2208 — concluded)

Archived: [`docs/archive/code-review-full-2026-08-20-2208.md`](archive/code-review-full-2026-08-20-2208.md). Do not treat as a work queue.

| Batch | IDs | Status |
|-------|-----|--------|
| P0 | H1, H2, H3 | ✅ Done |
| P1 | M2, M3, M4, M9 | ✅ Done |
| P2 | M5, M6, M8 | ✅ Done; M7 done later (pagination) |
| P3 | M10 | ✅ Done (grades, approval limits, reasons, `on_commit` stub) |
| P4 | M1 + L1–L14 | ✅ Done (L13 deferred); review **archived** |
| — | M7 | ✅ Done (console pagination, 2026-08-21) |

Plans (reference only): `.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md`, `fix_p1_m2-m9_387eec3a.plan.md`, `fix_p2_m5_m6_m8_2372dbfd.plan.md`, `p4_m1_l1-l14_71ae16a5.plan.md`.

---

## Locked decisions (do NOT re-litigate)

| # | Decision |
|---|----------|
| D1 | Selling prices are **manual**; cost price is **dynamic** (from supplier list) |
| D2 | 3 selling prices: retail / wholesale / special (not branch-tiered) |
| D3 | Supplier price linked by **supplier + item** |
| D4 | `SupplierItemPrice` table, `unique(supplier, item)` |
| D5 | Stock = **movement ledger** + cached quantity on `Item` |
| D6 | **Many receipts per PO** (partial shipments) |
| D7 | PO status: `draft → submitted → approved/rejected → received → closed` |
| D8 | Rappel = simple per-line % for now |
| D9 | Email = stub (`notify_supplier_on_approval`), deferred to Phase 6 |
| D10 | Branches **not built yet** — keep `Item` global (no `branch_id`); Phase 5 plan in progress |
| D11 | `primary` = preferred supplier; auto-suggested later; always overridable |
| D12 | **B-hard:** a PO line is **rejected** if the PO's supplier has no price for the item (no fallback to another supplier's price) |
| D13 | **Approved totals snapshot:** `approved_net`/`approved_vat`/`approved_gross` stored once at `approve()` (frozen financial record; lines stay computed) |
| D14 | **One primary** `SupplierItemPrice` per item — DB partial unique `unique_primary_supplier_item_price`; lock Item; clear other primaries **before** save |
| D15 | **Duplicate PO lines rejected** (`unique_po_line_item`) — do **not** merge quantities |
| D16 | **Inactive entities:** no PO create/submit/approve/add-line for inactive supplier or item; catalog (`active_only=True`) excludes inactive families; cannot assign items to an inactive family. Do **not** cascade-deactivate items when a family is deactivated |
| D17 | Warehouse groups are **code-owned**: `sync_warehouse_groups()` still `permissions.set()` (extras in `/admin/` wiped on migrate). `assign_warehouse_group` is **exclusive** (one warehouse group per user) and **resets `warehouse_grade` to 1** |
| D18 | **Warehouse grades:** operator 1–2, manager 1–3, admin unlimited. Operator 1 view-only; operator 2 / manager 1 mutate the closed circuit; manager 2+ approve. Operators never approve. Caps in `ApprovalLimit` (EUR **gross**); admin-only edit at `/manage/approval-limits/`. Seed defaults: manager 2 self 100 / others 5_000; manager 3 self 500 / others 50_000 |
| D19 | **PO/stock reasons:** reject, manual close (remaining qty), and `adjust_stock` require a non-empty reason. Full receipt auto-close uses `"Fully received"`; `receive()` logs `"Goods received"`. Submit/approve/reopen reasons optional but wired. Email stub via `transaction.on_commit` (Phase 6 still pending) |
| D20 | Selling prices & `reorder_level` must be **finite and ≥ 0** (0 allowed). Enforced in services (`_validate_non_negative`), `MinValueValidator(0)`, and DB `CheckConstraint`s |
| D21 | **Family names are immutable** — create-only. `name` is not an updatable field; the family PATCH API does not rename |
| D22 | `SupplierItemPrice` can only be created for an **active** supplier **and** item |
| D23 | `VatRate.rate` is a fraction in `[0, 1]` (DB `CheckConstraint`) |
| D24 | PO line quantity upper bound = `1e9` (matches inventory) |
| D25 | `User.timezone` validated (IANA) in `clean()`; middleware `finally: deactivate()` so the timezone never leaks across requests |
| D26 | Dashboard shows permission codenames only for superusers / `DEBUG` |
| D27 | **Login rate limiting is a pre-production blocker** — deferred (`django-axes` or proxy); documented in `settings.example.py` |
| D28 | **Money rounding:** `ROUND_HALF_UP` (half away from zero). Unit costs → 4 dp first, then monetary amounts (net / vat / gross) → 2 dp. Implemented via `procurement.models.round_money`; the future `orders` app must reuse it |
| — | Dates DD/MM/YYYY (24h); per-user timezone (default `Europe/Lisbon`); EN + pt-PT |

---

## What already landed (2208 — do not re-do)

**P0 — Highs**

- **H1** — `_lock_po()` before `add_line` / `update_line` / `remove_line` so line edits cannot race with submit/approve (D13 snapshot).
- **H2** — `accounts/authz.py`: `deny_if_inactive` / `user_is_active`. Django may treat an inactive session user as `AnonymousUser` while leaving `_auth_user_id`. Guards run **before** the auth check in all three `*_required` decorators; 403 `"Account is inactive"` + logout.
- **H3** — partial unique on primary supplier price; lock Item; clear other primaries before save. Migration `products/0006_unique_primary_supplier_item_price.py`.

**P1 — Mediums**

- **M3** — D12 price check on **submit and approve** (`_validate_all_lines_have_supplier_price`). Tests that delete a price must delete `SupplierItemPriceChangeLog` first (`PROTECT`).
- **M2** — `InactiveSupplierError` / `InactiveItemError` / `InactiveFamilyError`. Activity checks hit the DB (`filter(pk=..., is_active=True)`), not stale in-memory flags. `get_catalog(active_only=True)` also requires `family__is_active=True`.
- **M4** — `DuplicatePOLineError` + `unique_po_line_item` (`procurement/0004_unique_po_line_item.py`).
- **M9** — `_parse_int_id` (reject floats); add-line `DoesNotExist` → 404; `_write_movement` rejects balance ≥ 1e9.

**P2 — Mediums**

- **M5** — `CheckConstraint item_quantity_gte_zero` (`products/0007_item_quantity_gte_zero.py`); `inventory.services.ledger_quantity()`.
- **M6** — `receive_goods` locks items by sorted `pk` (`order_by("pk").select_for_update()`) before writing movements.
- **M8** — exclusive `assign_warehouse_group`; docstring on `sync_warehouse_groups`.

**P3 — M10**

- **Grades** — `User.warehouse_grade`; `accounts/capabilities.py` is the website source of truth (Django group perms are the coarse outer gate). Operators get add/change at group level; grade 1 is still view-only.
- **Approval limits** — `ApprovalLimit` / `ApprovalLimitChangeLog`; admin page `/manage/approval-limits/`. `approve()` enforces SoD + caps (admin unlimited).
- **Reasons** — required on `reject`, manual `close` (remaining qty), `adjust_stock`. Status changelog `reason` populated. Auto-close `"Fully received"`.
- **Email stub** — `transaction.on_commit(notify_supplier_on_approval)`; Phase 6 product not built.

**P4 — M1 + L1–L14 (review complete)**

- **M1** — `_validate_non_negative` for `reorder_level` + the three selling prices; `MinValueValidator(0)` + DB `CheckConstraint`s (`products/0008`).
- **L1** — non-empty `description` enforced in `create_item`/`update_item`.
- **L2** — family `name` removed from updatable fields + PATCH API.
- **L3** — `create_supplier_item_price` requires active supplier + item.
- **L4** — `VatRate.rate` in `[0, 1]`.
- **L5** — `line_vat` added to the line serializer.
- **L6** — console `_parse_decimal` now rejects NaN/Infinity (products + procurement).
- **L7** — PO `quantity` upper bound (1e9).
- **L8** — `User.clean()` timezone validation; middleware `finally: deactivate()`.
- **L9** — dashboard permission codenames hidden except superuser/DEBUG.
- **L10** — removed `StockMovement.Type.INITIAL` and `SupplierItemPriceChangeLog` DEACTIVATED/REACTIVATED (`inventory/0003`, `products/0008`).
- **L11** — removed unused `CHANGE_GOODS_RECEIPT`.
- **L12** — commented production-settings block in `settings.example.py`.
- **L13** — deferred (rate limiting) — documented blocker.
- **L14** — ledger-sum / concurrency / primary-race tests already present from H1/H3/M5.

**Seed bug (verified, fixed in `seed_dev_data`)**

`update_family()` returns a **new** `select_for_update` instance. The command stored the old object (`is_active=False`) after temporarily reactivating “Legacy stock”, so the follow-up pass skipped writing False and left the family **active**. A second seed then put LEG items in `get_catalog`.

Fix: `family = update_family(...)`; `refresh_from_db()` before the activity pass. Test: `test_second_seed_keeps_legacy_family_inactive`.

---

## Git (as of 21 Aug 2026, 21:06 WEST)

- Branch: **`phase5-branches`**. Slices 1 (tenancy), 2 (branch catalog), 3 (requisição), 4 (goods issue), and 5 (branch receipt + stock) are committed here; `main` tracks `origin/main`.
- The 1303 review fixes (N1–N12), **M7 console pagination**, and the `PROJECT-PLAN.md` rename are committed on `main`. The 1303 review is archived under `docs/archive/`.
- Working tree has local `.venv` noise — do **not** commit `.venv` deletions.

---

## Tests

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput
```

- Last full suite: **378 OK** without `--keepdb` (294 prior + 44 `branches` + 20 `orders` + 20 goods-issue/branch-receipt).
- Fast hasher when `TESTING`. Quiet logging in tests.
- `--keepdb` can go stale after `TransactionTestCase` (missing `VatRate` / similar). Recreate **without** `--keepdb` if the suite blows up on missing tables/rows.

---

## Key files

```
products/       catalogue + pricing (models, services, console_views, admin, tests)
procurement/    purchase orders (models, services, console_views, admin, permissions, tests)
inventory/      goods receipt + stock ledger (models, services, console_views, admin, permissions, tests)
accounts/       custom User, warehouse groups, grades, login, timezone middleware, authz.py, capabilities.py
branches/       tenancy: Branch + BranchMembership, ActiveBranchMiddleware, picker, capabilities, admin, tests
orders/         internal request (requisição interna): models, services, console API, web UI, admin, tests
config/         settings, urls
logging_utils/  rotating per-app logs
docs/           plan, handoff, archived reviews (incl. 1303), user-manuals/, tenancy design
```

**Conventions:** all mutations go through each app's `services.py`; audit-by-design (`*ChangeLog`); plain Django + vanilla JS; `select_for_update()` on updates.

---

## Run / test

```bash
source .venv/bin/activate
python manage.py migrate
./scripts/seed_dev_data.sh          # idempotent; VAT rates come from migration 0002
python manage.py runserver
.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput
```

- **Logins** (all `devpass123`): `warehouse.admin@centcompras.dev`, `warehouse.manager@…` / `manager2` / `manager3`, `warehouse.operator@…` / `operator2` (grades 1–3 as seeded). **Branch:** `branch.operator.north@…` / `branch.manager.north@…` / `branch.admin.north@…` (North), `branch.operator.south@…` / `branch.manager.south@…` (South), and `branch.dual@…` (both branches).
- **URLs:** `/` dashboard · `/manage/items/` item console · `/manage/catalog/` manager catalog · `/manage/purchase-orders/` PO console · `/manage/approval-limits/` PO caps (admin edit) · `/manage/goods-receipts/` goods receipt + stock · `/manage/internal-requests/` request queue + goods issue · `/manage/branch-approval-limits/` branch caps (admin edit) · `/branch/select/` branch picker · `/branch/catalog/` branch catalog (cost hidden) · `/branch/requests/` requisição interna · `/admin/` superuser only.

---

## Docs map

| Doc | Purpose |
|-----|---------|
| `README.md` | setup, URLs, seed, how to run |
| `docs/PROJECT-PLAN.md` | **Living plan** — sequencing + status tracker + locked decisions; tick its tracker every session |
| `docs/archive/code-review-full-2026-08-21-1303.md` | Follow-up review — **concluded & archived** (N1–N12 applied) |
| `docs/archive/code-review-full-2026-08-20-2208.md` | Full review — **concluded & archived** (P0–P4 done; L13 deferred) |
| `docs/archive/code-review-full-2026-08-20-1928.md` | Prior full review — concluded |
| `docs/archive/code-review-audit.md` | historical catalogue hardening |
| `docs/archive/code-review-2026-08-20.md` | Phase 2 review — concluded |
| `docs/archive/code-review-inventory-2026-08-20.md` | Phase 3 review — concluded |
| `docs/user-manuals/` | staff user manuals |
| `docs/archive/phase5-plan-260821-1756.md` | Phase 5 build spec (locks 1–10) — **archived** ✅ |
| `docs/archive/phase5-roadmap-260821-1618.md` | Phase 5 roadmap — **archived** ✅ |
| `docs/archive/phase5-brainstorm-260821-1530.md` | Phase 5 brainstorm + locked decisions (A1–B8) — **archived** ✅ |
| `docs/future-enhancements-260821-1833.md` | Future nice-to-haves (E items + later ideas) — parking lot, not Phase 5 |
| `docs/archive/warehouse-tenancy-setup.md` | **Archived** Branch/Membership sketch — superseded by brainstorm |
| `products/products_docs/aux_instructions.md` | learning pace for agents (not live status) |
| `.cursor/rules/` | agent rules — must match this handoff |
