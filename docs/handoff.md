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
| **4 — Manager catalog (stock + price view)** | ✅ **Done** |
| 5 — Branches + internal request | ⏸ Deferred |
| 6 — Email automation | ⏸ Pending (stub exists) |
| 7 — Mobile / offline / PWA / OAuth | ⏸ Future |

**Phases 0–4 are complete.** Remaining work is branches (deferred), email (pending), and mobile/offline/OAuth (future) — no forced "next" build after Phase 4.

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

## What's next (no forced build)

Phases 0–4 are complete (auth → catalogue → pricing → purchase orders → goods receipt → manager catalog). The remaining phases are **all deferred/pending/future**:

- **Phase 5 — branches + internal request** ⏸ deferred (needs its own branches plan).
- **Phase 6 — email automation** ⏸ pending (the `notify_supplier_on_approval` stub exists).
- **Phase 7 — mobile / offline / PWA / OAuth** ⏸ future.

There is no single "next" build after Phase 4. Next session, pick one to scope — **email (Phase 6) is the smallest self-contained item**; **branches (Phase 5) needs a dedicated plan**.

---

## Key files

```
products/       catalogue + pricing (models, services, console_views, admin, tests)
procurement/    purchase orders (models, services, console_views, admin, permissions, tests)
inventory/      goods receipt + stock ledger (models, services, console_views, admin, permissions, tests)
accounts/       custom User (email, timezone), warehouse groups, login, timezone middleware
config/         settings, urls
logging_utils/  rotating per-app logs
docs/           plan, handoff, code reviews, user-manuals/, tenancy design
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
- **URLs:** `/` dashboard · `/manage/items/` item console · `/manage/catalog/` manager catalog (stock + prices) · `/manage/purchase-orders/` PO console · `/manage/goods-receipts/` goods receipt + stock · `/admin/` superuser only.
- **Test state at sign-off:** full suite green (~190 tests: products 122 + accounts 16 + procurement 27 + inventory 25). Tests run fast (~18s) — `TESTING` flag in settings enables a fast password hasher + quiet logging.
- **Git:** branch `phase3-stock-ledger` (Phases 3–4 work — Phase 4 manager catalog is **uncommitted** in the working tree).

---

## Docs map

| Doc | Purpose |
|-----|---------|
| `README.md` | setup, URLs, seed, how to run |
| `docs/project-plan-2026-08-20.md` | phased plan + status tracker + locked decisions |
| `docs/archive/code-review-audit.md` | **historical / completed** — catalogue hardening; “Phase 1/2/3” = audit batches, not product phases |
| `docs/archive/code-review-2026-08-20.md` | Phase 2 review — **concluded** (all findings fixed); archived |
| `docs/archive/code-review-inventory-2026-08-20.md` | Phase 3 review — **concluded** (all findings fixed); archived |
| `docs/user-manuals/` | staff user manuals |
| `docs/user-manuals/01-items.md` | item console |
| `docs/user-manuals/02-purchase-orders.md` | purchase orders |
| `docs/user-manuals/03-goods-receipts.md` | goods receipt & stock |
| `docs/warehouse-tenancy-setup.md` | Phase 5 tenancy **design** — not built; **§6–7 Order is a sketch, NOT to implement** |
| `products/products_docs/aux_instructions.md` | learning pace for agents (not live status) |
| `.cursor/rules/` | agent rules — must match this handoff |
