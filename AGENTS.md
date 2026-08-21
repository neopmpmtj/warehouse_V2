# CentCompras — Agent instructions

Django 6.1 + PostgreSQL MVP for a **central warehouse** with **satellite branches**. Catalogue + pricing + purchase orders + goods receipt & stock + manager catalog (Phases 0–4) are done. Branches, orders, offline, and email are deferred.

**▶ Read [`docs/handoff.md`](docs/handoff.md) first** — condensed state, locked decisions, and the exact next task. Then [`README.md`](README.md) for setup, [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md) for sequencing, and the **live** review [`docs/code-review-full-2026-08-20-2208.md`](docs/code-review-full-2026-08-20-2208.md) (P0–P2 done; **next is P3 = M10**). Do **not** archive 2208 until remaining findings are done or deferred. The prior review is [`docs/archive/code-review-full-2026-08-20-1928.md`](docs/archive/code-review-full-2026-08-20-1928.md) (concluded).

## Session handoff (August 2026)

**Done:** Auth (email + warehouse groups + per-user timezone), catalog management + audit, item console, **pricing** (selling prices + `SupplierItemPrice`), **purchase orders** (`procurement` app: lines, discounts, approval workflow, approved-totals snapshot, email stub), **goods receipt + stock ledger** (`inventory` app: `GoodsReceipt`/`GoodsReceiptLine`, `StockMovement` signed ledger, cached `Item.quantity`, `receive_goods()` + admin-only `adjust_stock()`), **manager catalog** (read-only `/manage/catalog/`: stock + reorder level + selling/buying prices + suppliers, cost visible to warehouse groups only), dev seed script.

**Not done:** `orders` app, offline, shared chrome, branch phone UX, console polish, production OAuth/deployment, branches.

**Next:** finish the 2208 review — **P3 = M10** (policy: self-approval, close/adjust reasons, `on_commit` for the email stub), then M1 and L1–L14. M7 pagination stays deferred. Product phases 5–7 remain deferred/pending/future. Do **not** implement `orders/` or the tenancy-doc Order stub.

**Stock today:** `Item.quantity` is a cached balance written **only** via `StockMovement` (never typed directly); DB `CheckConstraint item_quantity_gte_zero`. Selling prices are **manual**; cost prices are **dynamic** from `SupplierItemPrice` (one `primary` per item, DB-enforced). PO lines are **rejected** if the supplier has no price for the item, or if the same item is added twice; `approved_net/vat/gross` are frozen at approval. Warehouse group assignment is exclusive.

## User roles (do not confuse these)

| Role | Flag / model | Catalog | Orders (future) |
|------|----------------|---------|-----------------|
| Warehouse admin | group `warehouse_admins` | Full catalogue (view/add/change/delete) via the website | N/A (central) |
| Warehouse manager | group `warehouse_managers` | View/add/change via the website (no delete) | N/A (central) |
| Warehouse operator | group `warehouse_data_operators` | Read-only catalogue on the website | N/A (central) |
| Branch admin/manager/user | *(future — Phase 5)* `BranchMembership.role` | Read-only catalogue (not built) | Per-branch permissions (not built) |
| Django superuser | `is_superuser` | May use the website console; **only** role that can log into `/admin/` | Site config in `/admin/` |

Dev seed: `./scripts/seed_dev_data.sh` → `warehouse.admin@centcompras.dev`, `warehouse.manager@centcompras.dev`, `warehouse.operator@centcompras.dev`, password `devpass123`.

## Current state (what exists)

### Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom `User` (email login, timezone), login/logout, warehouse groups, timezone middleware, `authz.py` (inactive-user guard) |
| `products` | Catalogue + pricing: model, service layer, API, staff admin, staff console, tests |
| `procurement` | Purchase orders: models, service layer, console API, admin, tests |
| `inventory` | Goods receipt + stock ledger: `GoodsReceipt`/`StockMovement`, services, console API, admin, tests |
| `branches` | ⚠️ **Not built yet** — deferred (designed in `docs/warehouse-tenancy-setup.md`) |
| `logging_utils` | `get_logger("centcompras.<app>")`, rotating logs in `logs/` |

### Auth

- `AUTH_USER_MODEL = "accounts.User"`
- Warehouse roles via Django groups: `warehouse_admins` / `warehouse_managers` / `warehouse_data_operators`
- Catalogue and API require login; API returns 401 when unauthenticated
- Google OAuth planned for production — not implemented in dev
- **Branches (tenancy) deferred** — `Branch`/`BranchMembership`/middleware/picker are designed but **not built** (no `branches/` app yet)

### Catalogue

- **Item fields:** family, optional `internal_code`, `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active` (new items start inactive), timestamps, plus **3 manual selling prices** (`retail_price`, `wholesale_price`, `special_price`) and a cached `quantity` balance (updated via `StockMovement`). Suppliers are independent master data.
- **Supplier prices:** `SupplierItemPrice` (supplier × item → `cost_price`, one `primary` per item) — the dynamic cost source for purchase orders.
- **Audit:** `ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog`, `SupplierItemPriceChangeLog` — who changed what (create / update / deactivate / reactivate). Item lifecycle reasons required; family/supplier deactivate is confirm-only
- **Names:** family and supplier names are case-insensitive unique; the console UI does not rename them
- **Global catalogue** — no `branch_id` on `Item`
- **Management:** warehouse users via `/manage/items/` (groups `warehouse_admins` / `warehouse_managers` / `warehouse_data_operators` and Django model permissions). Django admin (`/admin/`) is **superuser only**. All mutations through `products/services.py`
- **Validation:** duplicate non-empty `internal_code` rejected in services/admin
- **CLI:** `add_item` for dev/bootstrap (audit user is null); optional `--internal-code`
- **Tests:** `.venv/bin/python manage.py test products`

### Logging

- `logging_utils` — console + `logs/*.log` (gitignored)
- Loggers: `centcompras.products`, `centcompras.procurement`, `centcompras.inventory`, `centcompras.accounts`, `centcompras.django`, etc.
- Config: `logging_utils/logging_config.py`

PostgreSQL is the source of truth.

## Not implemented yet

- **Branches + internal request** (Phase 5, deferred)
- `orders` app and order workflow (**after** stock)
- Branches app (`Branch`, `BranchMembership`, middleware, picker)
- Order business rules not locked (stock timing, cart shape, cancel policy)
- Shared page chrome; branch phone-catalogue UX; staff console polish (dedicated sessions)
- Integration tests
- Google OAuth, public signup, password reset
- Email automation (supplier notification — stub exists)
- Offline order queue and sync; in-app branch switcher
- Catalog extras: categories, vector/LLM search, bulk import

Full list: [`README.md` → What is explicitly not built yet](README.md#what-is-explicitly-not-built-yet)

## Architecture conventions

```text
CLI / API / views  →  services.py  →  models.py  →  PostgreSQL
```

- Business logic in `services.py`, not views or management commands
- Catalog/PO/inventory management via Django groups + model permissions (`products`, `procurement`, `inventory` apps)
- Branch tenancy (`branches`, `request.active_branch`) is **future** — not built yet
- Plain Django + plain JavaScript — no React, Vue
- One concept per phase; no large application dumps

## Documentation conventions

- **Always put a full timestamp (date + time) in document filenames** — e.g. `code-review-full-2026-08-20-1928.md` (format `YYYY-MM-DD-HHMM`). The timestamp makes the chronological order self-evident when many similarly-named docs accumulate.
- Reviews/audits are worked to completion, marked done, then archived under `docs/archive/` — never left as a live backlog. The 2208 review is still live until M1, M10, and L1–L14 are done or deferred.

## Commands

```bash
source .venv/bin/activate
cp config/settings.example.py config/settings.py   # first time only
python manage.py migrate
python manage.py createsuperuser                 # optional site admin
./scripts/seed_dev_data.sh                         # warehouse users, families, suppliers, items, supplier prices
python manage.py runserver
python manage.py test products accounts procurement inventory --keepdb --noinput
```

**Tests:** always use the project virtualenv — do not use system `python`/`python3`. Either activate first (`source .venv/bin/activate`) or invoke the venv interpreter directly. Recreate without `--keepdb` if the test DB is stale after `TransactionTestCase`.

```bash
.venv/bin/python manage.py test products accounts procurement inventory --keepdb --noinput
```

Use one hostname consistently for offline testing (`localhost` or `127.0.0.1`, not both).

## Security

- Do not commit `config/settings.py`, `.env`, or credentials
- Do not add product creation or editing from the branch phone UI or public web unless explicitly requested

## Before large changes

1. [`docs/handoff.md`](docs/handoff.md) — state + decisions + next task
2. [`README.md`](README.md) — setup, URLs, seed
3. [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md) — phased plan
4. [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — tenancy design (**branches not built**); Order sketch §6–7 is **not** the next build
