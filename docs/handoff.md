# CentCompras — Session Handoff

> **Read this first when resuming work.** Last updated: 21 August 2026.

---

## TL;DR — where we are

| Phase | Status |
|-------|--------|
| 0 — Auth + catalogue identity + staff console | ✅ Done |
| 1 — Pricing (selling prices + supplier price list) | ✅ Done |
| 2 — Procurement (purchase orders) | ✅ Done |
| **3 — Goods receipt + stock ledger** | ✅ **Done** |
| **4 — Manager catalog (stock + price view)** | ✅ **Done** |
| 5 — Branches + internal request | ⏸ Deferred |
| 6 — Email automation | ⏸ Pending (stub exists) |
| 7 — Mobile / offline / PWA / OAuth | ⏸ Future |

**Phases 0–4 are complete.** Product phases 5–7 stay deferred/pending/future.

**Current work is not a new product phase.** It is the live full-codebase review [`docs/code-review-full-2026-08-20-2208.md`](code-review-full-2026-08-20-2208.md). **Do not archive that file** until every remaining ⏳ item is ✅ or ⏸ with rationale.

---

## Next session — do this

1. **Apply pending migrations** on the **dev** DB (test DB is applied by the suite):
   ```bash
   source .venv/bin/activate
   python manage.py migrate
   ```
   Expected if not already applied: `accounts.0003` (`warehouse_grade`), `procurement.0005` (`ApprovalLimit`). Also `products.0006`/`0007` and `procurement.0004` if those were skipped earlier.
2. **Continue the review at P4 = M1** (negative selling prices / reorder) and **L1–L14**.
3. **M7 (pagination) stays deferred** — consoles (`loadCatalog()` and similar) assume the full list is in memory. Do not paginate APIs without a frontend plan.

Do **not** start branches, orders, offline, shared chrome, or a full Phase 6 email product.

---

## Review progress (2208)

Live tracker: [`docs/code-review-full-2026-08-20-2208.md`](code-review-full-2026-08-20-2208.md). Prior concluded review: [`docs/archive/code-review-full-2026-08-20-1928.md`](archive/code-review-full-2026-08-20-1928.md).

| Batch | IDs | Status |
|-------|-----|--------|
| P0 | H1, H2, H3 | ✅ Done (committed on `main`) |
| P1 | M2, M3, M4, M9 | ✅ Done (committed on `main`) |
| P2 | M5, M6, M8 | ✅ Done (committed on `main`); M7 skipped |
| P3 | M10 | ✅ Done (grades, approval limits, reasons, `on_commit` stub) |
| P4 | M1 + L1–L14 | ⏳ **Next** |
| — | M7 | ⏸ Deferred (scale / frontend) |

Plans (reference only; do not treat as live status): `.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md`, `fix_p1_m2-m9_387eec3a.plan.md`, `fix_p2_m5_m6_m8_2372dbfd.plan.md`.

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
| D10 | Branches **not now** — keep products branch-ready |
| D11 | `primary` = preferred supplier; auto-suggested later; always overridable |
| D12 | **B-hard:** a PO line is **rejected** if the PO's supplier has no price for the item (no fallback to another supplier's price) |
| D13 | **Approved totals snapshot:** `approved_net`/`approved_vat`/`approved_gross` stored once at `approve()` (frozen financial record; lines stay computed) |
| D14 | **One primary** `SupplierItemPrice` per item — DB partial unique `unique_primary_supplier_item_price`; lock Item; clear other primaries **before** save |
| D15 | **Duplicate PO lines rejected** (`unique_po_line_item`) — do **not** merge quantities |
| D16 | **Inactive entities:** no PO create/submit/approve/add-line for inactive supplier or item; catalog (`active_only=True`) excludes inactive families; cannot assign items to an inactive family. Do **not** cascade-deactivate items when a family is deactivated |
| D17 | Warehouse groups are **code-owned**: `sync_warehouse_groups()` still `permissions.set()` (extras in `/admin/` wiped on migrate). `assign_warehouse_group` is **exclusive** (one warehouse group per user) and **resets `warehouse_grade` to 1** |
| D18 | **Warehouse grades:** operator 1–2, manager 1–3, admin unlimited. Operator 1 view-only; operator 2 / manager 1 mutate the closed circuit; manager 2+ approve. Operators never approve. Caps in `ApprovalLimit` (EUR **gross**); admin-only edit at `/manage/approval-limits/`. Seed defaults: manager 2 self 100 / others 5_000; manager 3 self 500 / others 50_000 |
| D19 | **PO/stock reasons:** reject, manual close (remaining qty), and `adjust_stock` require a non-empty reason. Full receipt auto-close uses `"Fully received"`; `receive()` logs `"Goods received"`. Submit/approve/reopen reasons optional but wired. Email stub via `transaction.on_commit` (Phase 6 still pending) |
| — | Dates DD/MM/YYYY (24h); per-user timezone (default `Europe/Lisbon`); EN + pt-PT |

---

## What landed this review (for the next agent)

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

**Seed bug (verified, fixed in `seed_dev_data`)**

`update_family()` returns a **new** `select_for_update` instance. The command stored the old object (`is_active=False`) after temporarily reactivating “Legacy stock”, so the follow-up pass skipped writing False and left the family **active**. A second seed then put LEG items in `get_catalog`.

Fix: `family = update_family(...)`; `refresh_from_db()` before the activity pass. Test: `test_second_seed_keeps_legacy_family_inactive`.

---

## Git (as of 21 Aug 2026)

- Branch: **`main`** (tracks `origin/main`). P0–P3 review fixes and this handoff are committed when you commit. Working tree may have local `.venv` noise — do **not** commit `.venv` deletions.
- Next product work: **P4 = M1 + L1–L14**. Do not archive `docs/code-review-full-2026-08-20-2208.md` until those are done or deferred.

---

## Tests

```bash
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```

- Last full suite: **249 OK** in ~87s with `--keepdb`.
- Fast hasher when `TESTING`. Quiet logging in tests.
- `--keepdb` can go stale after `TransactionTestCase` (missing `VatRate` / similar). Recreate **without** `--keepdb` if the suite blows up on missing tables/rows.

---

## Key files

```
products/       catalogue + pricing (models, services, console_views, admin, tests)
procurement/    purchase orders (models, services, console_views, admin, permissions, tests)
inventory/      goods receipt + stock ledger (models, services, console_views, admin, permissions, tests)
accounts/       custom User, warehouse groups, grades, login, timezone middleware, authz.py, capabilities.py
config/         settings, urls
logging_utils/  rotating per-app logs
docs/           plan, handoff, live 2208 review, user-manuals/, tenancy design
```

**Conventions:** all mutations go through each app's `services.py`; audit-by-design (`*ChangeLog`); plain Django + vanilla JS; `select_for_update()` on updates.

---

## Run / test

```bash
source .venv/bin/activate
python manage.py migrate
./scripts/seed_dev_data.sh          # idempotent; VAT rates come from migration 0002
python manage.py runserver
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```

- **Logins** (all `devpass123`): `warehouse.admin@centcompras.dev`, `warehouse.manager@…` / `manager2` / `manager3`, `warehouse.operator@…` / `operator2` (grades 1–3 as seeded).
- **URLs:** `/` dashboard · `/manage/items/` item console · `/manage/catalog/` manager catalog · `/manage/purchase-orders/` PO console · `/manage/approval-limits/` PO caps (admin edit) · `/manage/goods-receipts/` goods receipt + stock · `/admin/` superuser only.

---

## Docs map

| Doc | Purpose |
|-----|---------|
| `README.md` | setup, URLs, seed, how to run |
| `docs/project-plan-2026-08-20.md` | phased plan + status tracker + locked decisions |
| **`docs/code-review-full-2026-08-20-2208.md`** | **LIVE review backlog** — P0–P3 done; P4 next; do not archive yet |
| `docs/archive/code-review-full-2026-08-20-1928.md` | Prior full review — concluded |
| `docs/archive/code-review-audit.md` | historical catalogue hardening |
| `docs/archive/code-review-2026-08-20.md` | Phase 2 review — concluded |
| `docs/archive/code-review-inventory-2026-08-20.md` | Phase 3 review — concluded |
| `docs/user-manuals/` | staff user manuals |
| `docs/warehouse-tenancy-setup.md` | Phase 5 tenancy **design** — not built; **§6–7 Order is a sketch, NOT to implement** |
| `products/products_docs/aux_instructions.md` | learning pace for agents (not live status) |
| `.cursor/rules/` | agent rules — must match this handoff |
