# CentCompras — Session Handoff

> **Read this first when resuming work.** Last updated: 20 August 2026.

---

## TL;DR — where we are

| Phase | Status |
|-------|--------|
| 0 — Auth + catalogue identity + staff console | ✅ Done |
| 1 — Pricing (selling prices + supplier price list) | ✅ Done |
| 2 — Procurement (purchase orders) | ✅ Done |
| **3 — Goods receipt + stock ledger** | ✅ **Done** |
| **4 — Manager catalog (stock + price view)** | ▶ **NEXT** |
| 5 — Branches + internal request | ⏸ Deferred |
| 6 — Email automation | ⏸ Pending (stub exists) |
| 7 — Mobile / offline / PWA / OAuth | ⏸ Future |

**What we build next: Phase 4** — a join-heavy, read-only **manager catalog**: item + 3 selling prices + buying price (primary supplier, O1) + cached stock balance + reorder level + supplier(s). Cost **visible** to warehouse groups only; reorder-level highlighting.

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
| — | Dates DD/MM/YYYY (24h); per-user timezone (default `Europe/Lisbon`); EN + pt-PT |

---

## The exact next task (Phase 4)

**Manager catalog (stock + price view)** — full spec in [`project-plan-2026-08-20.md` §11](project-plan-2026-08-20.md).

- Read-only, join-heavy dashboard joining `Item`, `SupplierItemPrice`, `StockMovement` (cached `quantity`), and `Supplier`.
- Cost **visible** to warehouse groups only (branch view hides cost — Phase 5).
- Reorder-level highlighting (below `reorder_level` → flag).
- Do **not** start branches, orders, offline, email, or shared page chrome in passing.

---

## Key files

```
products/       catalogue + pricing (models, services, console_views, admin, tests)
procurement/    purchase orders (models, services, console_views, admin, permissions, tests)
inventory/      goods receipt + stock ledger (models, services, console_views, admin, permissions, tests)
accounts/       custom User (email, timezone), warehouse groups, login, timezone middleware
config/         settings, urls
logging_utils/  rotating per-app logs
docs/           plan, handoff, code reviews, user manual, tenancy design
```

**Conventions:** all mutations go through each app's `services.py`; audit-by-design (`*ChangeLog`); plain Django + vanilla JS; `select_for_update()` on updates.

---

## Run / test

```bash
source .venv/bin/activate
python manage.py migrate
./scripts/seed_dev_data.sh          # idempotent; VAT rates come from migration 0002
python manage.py runserver
python manage.py test products accounts procurement inventory
```

- **Logins** (all `devpass123`): `warehouse.admin@centcompras.dev`, `warehouse.manager@…`, `warehouse.operator@…` (groups `warehouse_admins`/`_managers`/`_data_operators`).
- **URLs:** `/` dashboard · `/manage/items/` item console · `/manage/purchase-orders/` PO console · `/manage/goods-receipts/` goods receipt + stock · `/admin/` superuser only.
- **Test state at sign-off:** full suite green (~170 tests: products 113 + accounts 16 + procurement 27 + inventory 14). Tests run fast (~18s) — `TESTING` flag in settings enables a fast password hasher + quiet logging.
- **Git:** branch `phase3-stock-ledger` (Phase 3 committed on top of `main`).

---

## Docs map

| Doc | Purpose |
|-----|---------|
| `README.md` | canonical project status + setup (read §Project status) |
| `docs/project-plan-2026-08-20.md` | phased plan + status tracker (tick as you go) |
| `docs/code-review-2026-08-20.md` | recent review findings (mostly fixed) |
| `docs/code-review-audit.md` | earlier (Phase 1) audit |
| `docs/user-manual.md` | user manual — item console |
| `docs/user-manual-purchase-orders.md` | user manual — purchase orders |
| `docs/warehouse-tenancy-setup.md` | tenancy design — **§6–7 Order is a sketch, NOT to implement** |
