# CentCompras — Central Warehouse

A Django web application for a company with a **central warehouse** and **satellite branches**. Warehouse staff manage the catalogue, purchase orders, and goods receipt today. Branch staff will later browse the catalogue from a phone browser and place orders against central stock — including in areas with poor mobile coverage.

This repository is an early-stage MVP built incrementally: one concept per phase, with clear separation of responsibilities and no unnecessary frameworks.

---

## Project status

*Last updated: 20 August 2026.*

Phases 0–4 are done (auth, catalogue, pricing, purchase orders, goods receipt + stock ledger, manager catalog). Branches, orders, offline, and email are deferred.

> **Pick up here:** [`docs/handoff.md`](docs/handoff.md) — condensed state, locked decisions, and the exact next task. Sequencing: [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md).

### User roles (practice with these)

| User type | Example (after seed) | Can do today |
|-----------|----------------------|--------------|
| **Warehouse admin** | `warehouse.admin@centcompras.dev` | Full catalogue, POs (including approve), goods receipts, stock adjust (`warehouse_admins`). Cannot log into `/admin/`. |
| **Warehouse manager** | `warehouse.manager@centcompras.dev` | Add/edit catalogue and POs (submit, no approve); create goods receipts. No delete / no stock adjust. |
| **Warehouse operator** | `warehouse.operator@centcompras.dev` | Read-only catalogue, POs, and receipts. |
| **Branch users** | *(not seeded — Phase 5)* | Future: read-only catalogue and branch orders. |
| **Django superuser** | from `createsuperuser` | Site admin at `/admin/` only. The only users who may use Django admin. |

After `./scripts/seed_dev_data.sh`, seeded users share password **`devpass123`**. The seed does **not** create a superuser or any branch.

**Procurement:** admins create + **approve** POs; managers create + submit; operators view. **Stock:** admins may `adjust_stock`; managers/admins record goods receipts.

### Recommended next session

1. Read [`docs/handoff.md`](docs/handoff.md) and the plan [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md).
2. Fresh environment: `python manage.py migrate`, `./scripts/seed_dev_data.sh`, and `createsuperuser` (the seed does not create one).
3. Practice: warehouse user → `/manage/items/`, `/manage/purchase-orders/`, `/manage/goods-receipts/`.
4. Pick the next piece of work — email (Phase 6, smallest) or a branches plan (Phase 5). No forced next build after Phase 4.
5. Do **not** in passing: branches, orders, offline, email, shared page chrome.

---

## Business scenario

A central warehouse holds the master product catalogue and stock. Stock is a **movement ledger**: goods receipts write `StockMovement` rows and update cached `Item.quantity`. Quantity is never typed on the item form.

Satellite branches will later order against that stock. The `branches` app and orders are **future** (Phase 5). PostgreSQL is the **source of truth**.

Warehouse staff work at `/manage/items/`, `/manage/purchase-orders/`, and `/manage/goods-receipts/` via groups `warehouse_admins`, `warehouse_managers`, and `warehouse_data_operators`. Django admin is reserved for superusers.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django 6.1 |
| Database | PostgreSQL (`centcompras_db`) |
| Frontend | Plain HTML, plain JavaScript |
| Offline | (future — not implemented; previously removed) |
| Logging | `logging_utils` — console + rotating files in `logs/` |

No React, Vue, or similar frontend framework.

---

## What works today

### Authentication

- Custom `User` model (`accounts`) — email login, no username field; optional per-user timezone (default `Europe/Lisbon`)
- Session login/logout at `/accounts/login/` and `/accounts/logout/`
- Warehouse roles via Django groups
- Django admin (superuser only) for users and groups
- Consoles and APIs require login; APIs return 401 when unauthenticated

> **Branches (tenancy) are not built.** Design is in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md). There is no `branches/` directory.

Production will use Google OAuth (not implemented in dev).

### Item catalogue

- `Item`: family, optional `internal_code`, `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active` (new items start inactive), three **manual** selling prices (`retail_price`, `wholesale_price`, `special_price`), cached `quantity` (ledger only).
- `SupplierItemPrice`: supplier × item → `cost_price` + `primary` (one primary per item). Dynamic cost source for purchase orders.
- Family and supplier names are case-insensitive unique. The console UI does not rename them.
- Audit: `ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog`, `SupplierItemPriceChangeLog`.
- All mutations through [`products/services.py`](products/services.py).
- CLI (dev/bootstrap): `python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16`

### Consoles

- `/` — staff dashboard
- `/manage/items/` — items, families, suppliers, selling prices, supplier prices
- `/manage/catalog/` — read-only manager catalog: stock, reorder level, selling + buying price, suppliers (cost visible to warehouse groups only)
- `/manage/purchase-orders/` — POs, lines, discounts, submit/approve; a line is **rejected** if the supplier has no price for the item
- `/manage/goods-receipts/` — receipts (partial OK), stock movements, admin stock adjust
- Supplier email on PO approval is a **stub** (Phase 6)

### URL layout

| Path | Purpose |
|------|---------|
| `/` | Staff dashboard (catalogue view permission) |
| `/manage/items/` | Warehouse item console |
| `/manage/catalog/` | Manager catalog (stock + price view, read-only) |
| `/manage/purchase-orders/` | Purchase-order console |
| `/manage/goods-receipts/` | Goods receipt + stock console |
| `/api/manage/items/` | Item JSON API |
| `/api/manage/catalog/` | Manager catalog JSON API (joined stock + prices) |
| `/api/manage/families/` | Family JSON API |
| `/api/manage/suppliers/` | Supplier JSON API |
| `/api/manage/supplier-prices/` | Supplier price JSON API |
| `/api/manage/purchase-orders/` | Purchase-order JSON API (approve needs `can_approve`) |
| `/api/manage/goods-receipts/` | Goods receipt JSON API |
| `/api/manage/purchase-orders/<id>/receipt-summary/` | Per-line ordered/received/remaining |
| `/api/manage/stock-movements/` | Stock movement ledger (`?item_id=` filter) |
| `/api/manage/stock-adjustments/` | Manual stock adjustment (POST; `can_adjust_stock`) |
| `/accounts/login/` | Email + password login |
| `/accounts/logout/` | Log out |
| `/admin/` | Django admin (**superuser only**) |

There is no `GET /api/products/` and no `/service-worker.js`.

---

## Project structure

```text
warehouse/
├── manage.py
├── requirements.txt
├── config/                   # settings.example.py (copy to settings.py), urls.py
├── accounts/                 # custom User (email, timezone), login/logout, groups, middleware
├── products/                 # catalogue + pricing
├── procurement/              # purchase orders
├── inventory/                # goods receipt + stock ledger
├── logging_utils/            # console + logs/
├── docs/                     # handoff, plan, reviews, user manuals, tenancy design
├── scripts/                  # seed_dev_data.sh
├── AGENTS.md                 # agent instructions
└── .cursor/                  # Cursor rules
```

[`products/README.md`](products/README.md) is a **historical** catalogue build log.

---

## Setup

First-time setup from a fresh clone. Run all commands from the project root.

### 1. Virtual environment and dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL

The app expects database `centcompras_db` and user `postgres` (local dev). Adjust in `config/settings.py` if your setup differs.

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE centcompras_db;
ALTER USER postgres WITH PASSWORD 'your_password_here';
\q
```

### 3. Django settings

`config/settings.py` is gitignored. Copy the example and set the database password:

```bash
cp config/settings.example.py config/settings.py
```

`SECRET_KEY`, `DEBUG`, and `POSTGRES_PASSWORD` can come from environment variables (see the example file). Dev fallbacks exist for localhost.

### 4. Migrate and create site admin

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # prompts for email + password (not username)
```

`createsuperuser` creates a **site admin** for `/admin/`. That user cannot use the warehouse consoles until you add them to a warehouse group (or use a seeded warehouse user).

### 5. Seed test data

```bash
chmod +x scripts/seed_dev_data.sh   # first time only
./scripts/seed_dev_data.sh
```

This creates (idempotent):

| Item | Details |
|------|---------|
| **Warehouse users** | `warehouse.admin@…` / `warehouse.manager@…` / `warehouse.operator@…` |
| **Families, suppliers, items, supplier prices** | sample catalogue via `products/services.py` |
| **Password** | `devpass123` (override with `--password`) |

It does **not** create branches, branch users, or a Django superuser. Options: `--skip-items`, `--skip-warehouse`.

Items can also be added in `/manage/items/` or:

```bash
python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16
```

### 6. Test the application

1. Open `http://localhost:8000/` — redirected to login.
2. Log in as `warehouse.admin@centcompras.dev` / `devpass123`.
3. Open `/manage/items/`, `/manage/purchase-orders/`, `/manage/goods-receipts/`.

Use **one hostname** consistently (`localhost` **or** `127.0.0.1`, not both).

### 7. Logging

Logs go to `logs/` (gitignored):

| File | Logger name |
|------|-------------|
| `logs/centcompras.log` | General |
| `logs/accounts.log` | `centcompras.accounts` |
| `logs/products.log` | `centcompras.products` |
| `logs/procurement.log` | `centcompras.procurement` |
| `logs/inventory.log` | `centcompras.inventory` |
| `logs/django.log` | `centcompras.django` (HTTP requests) |

```python
from logging_utils import get_logger

logger = get_logger("centcompras.products")
logger.info("Something happened")
```

Configuration: `logging_utils/logging_config.py`.

### Quick reference (daily dev)

```bash
source .venv/bin/activate
python manage.py runserver
```

First-time or reset DB: steps 1–4, then `./scripts/seed_dev_data.sh`.

Practice logins: `warehouse.admin@centcompras.dev`, `warehouse.manager@centcompras.dev`, `warehouse.operator@centcompras.dev` — password `devpass123`.

Tests:

```bash
.venv/bin/python manage.py test products accounts procurement inventory
```

Migrations: `accounts/0001–0002`, `products/0001–0005` (quantity is `0005`), `procurement/0001–0003`, `inventory/0001–0002`. Run `migrate` after pull if schema changed.

---

## Architecture (current)

```text
PostgreSQL
    ↑
User, Item, FamilyProduct, Supplier, SupplierItemPrice,
PurchaseOrder(+lines), GoodsReceipt(+lines), StockMovement
    ↑
services.py / permissions.py   (all mutations)
    ↑
views (login required) → API + HTML
    (item console, PO console, goods-receipt console)
```

---

## Further reading

- **Start here:** [`docs/handoff.md`](docs/handoff.md)
- [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md) — phased plan + status tracker
- [`docs/archive/code-review-inventory-2026-08-20.md`](docs/archive/code-review-inventory-2026-08-20.md) — Phase 3 review (concluded)
- [`docs/archive/code-review-2026-08-20.md`](docs/archive/code-review-2026-08-20.md) · [`docs/archive/code-review-audit.md`](docs/archive/code-review-audit.md) — archived reviews
- [`docs/user-manuals/01-items.md`](docs/user-manuals/01-items.md) · [`docs/user-manuals/02-purchase-orders.md`](docs/user-manuals/02-purchase-orders.md) · [`docs/user-manuals/03-goods-receipts.md`](docs/user-manuals/03-goods-receipts.md)
- [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — Phase 5 design; **§6–7 Order is a sketch, NOT to implement**
- [`AGENTS.md`](AGENTS.md)
- [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — development pace
- [`products/README.md`](products/README.md) — historical catalogue build log

---

## What is explicitly not built yet

Canonical list of “next / later” is the phase table in [`docs/handoff.md`](docs/handoff.md). In short:

- **Branches + internal request** (Phase 5)
- **Orders workflow** after that — do not implement the tenancy-doc `item_name` stub
- Email automation (stub exists), offline / PWA / OAuth, shared chrome, console polish
- Integration tests (unit suites are green, ~190 tests)
- Frontend pagination UI (API supports `?page`; console still loads all items)
