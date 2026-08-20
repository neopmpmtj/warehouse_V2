# CentCompras — Central Warehouse

A Django web application for a company with a **central warehouse** and **satellite branches**. Branch staff browse the product catalogue from a phone browser and will eventually place orders against central stock — including in areas with poor mobile coverage.

This repository is an early-stage MVP built incrementally: one concept per phase, with clear separation of responsibilities and no unnecessary frameworks.

---

## Project status (handoff)

*Last updated: 19 August 2026 — read this section first when resuming work.*

### Where we stand

**Purchase orders (Phase 2) are done.** Warehouse staff raise purchase orders against suppliers: lines auto-cost from the supplier's price list (a line is **rejected** if the supplier has no price for the item), three discount types (commercial / financial / rappel), an approval workflow (draft → submitted → approved/rejected → received → closed), and an approved-totals snapshot (net / VAT / gross) frozen at approval. Items and pricing (Phase 1) are also complete: items carry three **manual** selling prices and suppliers carry **cost prices** in `SupplierItemPrice`.

**There is still no stock** — quantity does not exist yet. The **next phase is the goods receipt + stock ledger**: recording goods received against an approved PO writes stock. Branch orders wait until then.

> ▶ **Pick up here:** [`docs/handoff.md`](docs/handoff.md) — condensed state + locked decisions + the exact next task.

### Completed

| Phase | Status | Notes |
|-------|--------|-------|
| **Product catalogue MVP** | Done | Model, API — see [`products/README.md`](products/README.md) |
| **Auth foundation** | Done | `accounts` (email login), warehouse groups |
| **Login-protected catalogue** | Done | `/` and `/api/products/` require session; API returns 401 when logged out |
| **Centralized logging** | Done | `logging_utils` → rotating files in `logs/` |
| **Catalog management & audit** | Done | Item / family / supplier lifecycle, `ItemChangeLog` + `FamilyChangeLog` + `SupplierChangeLog`, soft delete, staff admin via `products/services.py` |
| **Catalog polish** | Done | Duplicate `internal_code` validation; optional item audit `reason` |
| **Staff item console** | Done | `/manage/items/` — table, filters, column sort, inactive-by-default create + Genesis, family/supplier drawers, EN/pt-PT, light/dark |
| **Family & supplier priors** | Done | Console create/deactivate; case-insensitive unique names (no rename in the console UI); PostgreSQL audit logs |
| **Pricing (selling + supplier cost)** | Done | 3 manual selling prices on `Item`; `SupplierItemPrice` (supplier × item cost, one primary) + audit; console, admin, API, seed |
| **Purchase orders (procurement)** | Done | New `procurement` app: `PurchaseOrder` + lines, 3 discount types, approval workflow, approved totals snapshot (net/VAT/gross), email stub, console at `/manage/purchase-orders/` |
| **Timezone + dates** | Done | Per-user timezone (default `Europe/Lisbon`) + middleware; DD/MM/YYYY dates |
| **Dev seed script** | Done | [`scripts/seed_dev_data.sh`](scripts/seed_dev_data.sh) — warehouse users, families, suppliers, items, supplier prices |
| **Project setup docs** | Done | Root README, `requirements.txt`, `config/settings.example.py`, `AGENTS.md`, `.cursor/` rules |

**Design choices locked in for later phases:**

- `Item` catalogue is **global** (central warehouse) — no `branch_id` on items.
- **Catalog mutations** = warehouse groups on the website (`warehouse_admins` full, `warehouse_managers` add/change, `warehouse_data_operators` view). **`/admin/` is superuser only.**
- Dev login: email + password. Production: **Google OAuth** (not implemented yet).
- Users are provisioned in admin or seed script — no public signup.
- Orders (future, after inbound stock) will be **branch-scoped** with `branch` + `created_by` FKs. The sketch in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6 is **not** an implementation spec (`item_name` is leftover).
- **Items have no stock field** (inbound receipts will become the source of quantity later). Selling prices are **manual**; **cost prices are dynamic** from `SupplierItemPrice`.
- **Purchase orders:** status `draft → submitted → approved/rejected → received → closed`; 3 line discounts (commercial/financial/rappel, combined ≤ 100%); a PO line is **rejected** if the supplier has no price for the item (no cross-supplier fallback); `approved_net`/`approved_vat`/`approved_gross` are frozen at approval.

### User roles (important — practice with these)

| User type | Example (after seed) | Can do today |
|-----------|----------------------|--------------|
| **Warehouse admin** | `warehouse.admin@centcompras.dev` | Full catalogue on `/manage/items/` (`warehouse_admins`). Cannot log into `/admin/`. |
| **Warehouse manager** | `warehouse.manager@centcompras.dev` | Add/edit catalogue (`warehouse_managers`). No delete permission. |
| **Warehouse operator** | `warehouse.operator@centcompras.dev` | Read-only catalogue (`warehouse_data_operators`). |
| **Branch admin** | `admin.lisbon@centcompras.dev` | Log in, browse catalogue at `/` (read-only); future: orders in their branch (after inbound stock exists) |
| **Branch manager / user** | (create in admin) | Same browse access; different order permissions later |
| **Django superuser** | from `createsuperuser` | Site admin at `/admin/`: users, groups, memberships. The only users who may use the Django admin. |

After `./scripts/seed_dev_data.sh`, all seeded users share password **`devpass123`**.

**Procurement permissions:** warehouse **admins** create + **approve** POs; **managers** create + submit (no approve); **operators** view only.

### Not started / pending

| Area | Priority | Notes |
|------|----------|-------|
| **Goods receipt + stock ledger** | **Next (Phase 3)** | Recording goods received against an approved PO writes stock; stock becomes a movement ledger (`StockMovement`) with a cached `Item.quantity`. No app yet — see [`docs/handoff.md`](docs/handoff.md). |
| **Orders workflow** | After inbound stock | Branch requests against central stock. Sketch only: [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6–7. Do not implement the stub `item_name` model. |
| **Order business rules** | Before coding orders | Multi-line cart vs single line; stock decrement timing; cancel/edit policy |
| **Shared page chrome** | Later session | Same header/CSS on login, branch picker, `/`, so new pages do not look like a different app |
| **Branch phone catalogue UX** | Later session | Search, family, unit, human stock/price — hold; `/` stays a scaffold until that session |
| **Staff console polish** | Later session | History diffs, default Active filter, Genesis copy — hold |
| **Tests** | Later | `products` + `procurement` + `accounts` suites green (~156 tests); integration tests not started |
| **Integration tests** | Later | Full auth → branch middleware → catalogue API → offline flow |
| **Google OAuth** | Production | `django-allauth` or similar |
| **Public signup / password reset** | Later | |
| **Branch switcher in catalogue** | Later | Multi-branch users pick at login only; no in-app switch |
| **Production deployment** | Later | HTTPS, env secrets, PWA manifest |
| **Catalog extras (deferred)** | Later | Categories extras, LLM/vector search on `description`, bulk import |

### Recommended next session

1. Read [`docs/handoff.md`](docs/handoff.md) (condensed state + decisions) and the plan [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md).
2. Fresh environment: `python manage.py migrate`, `./scripts/seed_dev_data.sh`, and create a superuser with `createsuperuser` (the seed does not create one).
3. Practice: warehouse user → `/manage/items/` (items, families, suppliers, supplier prices) and `/manage/purchase-orders/` (create PO → add line → submit → approve).
4. **Start Phase 3 (goods receipt + stock ledger)** — see plan §10 and the handoff's "exact next task".
5. Do **not** in passing: branches, orders, offline, email, shared page chrome.

### Key files

```text
products/models.py           Item, FamilyProduct, Supplier, VatRate, SupplierItemPrice, change-log models
products/services.py         item / family / supplier / supplier-price mutations
products/console_views.py    item console API (/api/manage/*)
products/tests.py            catalogue + pricing tests
procurement/models.py        PurchaseOrder, PurchaseOrderLine, PurchaseOrderChangeLog
procurement/services.py      PO lifecycle, lines, discounts, approval, approved-totals snapshot
procurement/console_views.py PO console API
procurement/tests.py         procurement tests
accounts/groups.py           warehouse groups (products + procurement apps)
accounts/middleware.py       per-user timezone
products/management/commands/seed_dev_data.py
scripts/seed_dev_data.sh     wrapper: migrate + seed
```

Migrations: `products/0001–0004`, `procurement/0001–0002` (approved totals), `accounts/0001–0002` (timezone). Run `migrate` after pull if schema changed.

### Development philosophy

One concept per phase. Reusable `services.py` layer. Plain Django + plain JavaScript. Do not dump a finished application in one step. See [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md).

---

## Business scenario

- A central warehouse holds the master product catalogue and stock levels. **Stock does not exist yet** — the next phase (goods receipt) records supplier receipts so quantity is filled from purchases, not typed on a product.
- Branch users (satellite branches) will later order against central stock. Branches and orders are **future** (deferred).
- PostgreSQL on the server is the **source of truth**.

Warehouse staff manage the catalogue at `/manage/items/` and purchase orders at `/manage/purchase-orders/` via three Django groups (`warehouse_admins`, `warehouse_managers`, `warehouse_data_operators`). Django admin is reserved for superusers.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django 6.1 |
| Database | PostgreSQL (`centcompras_db`) |
| Frontend | Plain HTML, plain JavaScript |
| Offline | (future — not implemented) |
| Logging | `logging_utils` — console + rotating files in `logs/` |

No React, Vue, or similar frontend framework.

---

## What works today

### Authentication

- Custom `User` model (`accounts`) — email login, no username field
- Session login/logout at `/accounts/login/` and `/accounts/logout/`
- Warehouse roles via Django groups (`warehouse_admins` / `warehouse_managers` / `warehouse_data_operators`)
- Django admin (superuser only) for users and groups
- Catalogue requires login; API returns 401 when unauthenticated

> **Branches (tenancy) are NOT built yet.** The `branches` app (`Branch`, `BranchMembership`, active-branch middleware, picker) is documented in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) but **deferred** until after inbound stock. There is no `branches/` directory in the code today.

Production will use Google OAuth (not implemented in dev — email/password login only).

### Item catalogue (server)

- `Item` model: required `family`, optional `internal_code`, `description`, `unit_of_measure`, `reorder_level`, `vat_rate`, `is_active` (soft delete; **new items start inactive**), timestamps, plus three **manual selling prices** — `retail_price`, `wholesale_price`, `special_price`. No stock.
- `SupplierItemPrice` model: `supplier` × `item` → `cost_price` + `primary` (one primary per item). This is the **dynamic cost source** for later purchase orders. Audit via `SupplierItemPriceChangeLog`.
- `FamilyProduct` / `Supplier` — family is required on item create; suppliers are independent master data (not linked to items yet). Names are case-insensitive unique. The console UI does not rename them.
- Audit: `ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog` — who changed what (create / update / deactivate / reactivate). Item deactivate/reactivate require a reason; family/supplier lifecycle does not.
- Service layer in [`products/services.py`](products/services.py): item, family, and supplier mutations.
- Warehouse staff manage the catalogue in `/manage/items/` using Django model permissions on three groups. Django admin is superuser only.
- Dev/bootstrap CLI:

  ```bash
  python manage.py add_item "Cement 50kg" --family Cement --vat-rate VAT16
  python manage.py add_item "Steel Pipe" --family Pipes --vat-rate VAT16 --internal-code PIPE-20
  ```

- Staff JSON APIs (authenticated warehouse groups):

  ```text
  GET /api/manage/items/
  GET /api/manage/families/
  GET /api/manage/suppliers/
  ```

- `ItemChangeLog.reason` — required for item deactivate/reactivate; optional on field edits. Family/supplier logs store an empty reason today.
- Duplicate non-empty `internal_code` values are rejected with a clear validation error in admin and services.
- Tests in [`products/tests.py`](products/tests.py) cover service diffs, active filtering, uniqueness, console APIs, and audit logs.

### Item console (browser)

- Staff dashboard at `/` (catalogue view permission required).
- Item console at `/manage/items/` — table, filters, family and supplier drawers, selling prices, supplier prices.
- The console is online-only.

### Purchase orders (browser)

- Purchase-order console at `/manage/purchase-orders/` — list, create, line editor (auto-cost from the supplier price list; a line is rejected if the supplier has no price for the item), 3 discount types, status workflow, approved totals snapshot (net/VAT/gross), history, EN/pt-PT.
- Permissions: admins create + approve; managers create + submit; operators view.
- Supplier email notification on approval is a **stub** (Phase 6).

### URL layout

| Path | Purpose |
|------|---------|
| `/` | Staff dashboard (catalogue view permission) |
| `/manage/items/` | Warehouse item console (view permission) |
| `/manage/purchase-orders/` | Purchase-order console (view permission) |
| `/api/manage/items/` | Warehouse item JSON API (view; writes need add/change) |
| `/api/manage/families/` | Warehouse family JSON API (view; writes need add/change) |
| `/api/manage/suppliers/` | Warehouse supplier JSON API (view; writes need add/change) |
| `/api/manage/supplier-prices/` | Supplier price JSON API (view; writes need add/change) |
| `/api/manage/purchase-orders/` | Purchase-order JSON API (view; writes need add/change; approve needs `can_approve`) |
| `/accounts/login/` | Email + password login |
| `/accounts/logout/` | Log out |
| `/admin/` | Django admin (**superuser only**) |

---

## Project structure

```text
warehouse/
├── manage.py
├── requirements.txt
├── config/                   # settings.example.py (copy to settings.py), urls.py
├── accounts/                 # custom User (email, timezone), login/logout, groups, middleware
├── products/                 # catalogue + pricing app
├── procurement/              # purchase orders app
├── logging_utils/            # centralized logging (console + logs/)
├── docs/                     # handoff, plan, code reviews, user manual, tenancy design
├── scripts/                  # seed_dev_data.sh
├── AGENTS.md                 # agent instructions
└── .cursor/                  # Cursor rules and commands
```

The `products/README.md` file is a step-by-step record of how the catalogue and offline layer were built.

---

## Setup

First-time setup from a fresh clone. Run all commands from the project root (`warehouse/`).

### 1. Virtual environment and dependencies

```bash
cd warehouse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. PostgreSQL

The app expects database `centcompras_db` and user `postgres` (local dev). Adjust in `config/settings.py` if your setup differs.

Enter PostgreSQL as the `postgres` system user:

```bash
sudo -u postgres psql
```

Create the database:

```sql
CREATE DATABASE centcompras_db;
```

If you need to set or reset the `postgres` user password (must match `config/settings.py`):

```sql
ALTER USER postgres WITH PASSWORD 'your_password_here';
\q
```

### 3. Django settings

`config/settings.py` is gitignored (may contain credentials). Copy the example and edit it:

```bash
cp config/settings.example.py config/settings.py
```

Edit `config/settings.py` — set your real database password:

```python
DATABASES = {
    "default": {
        ...
        "PASSWORD": "your_actual_password",  # same as postgres user above
        ...
    }
}
```

### 4. Migrate and create site admin

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # prompts for email + password (not username)
```

`createsuperuser` creates a **site admin** for `/admin/`. That user can manage branches and users but **cannot browse the catalogue** until you also add a `BranchMembership` (step 5).

### 5. Seed test data

**Quick seed (recommended for local learning):**

```bash
chmod +x scripts/seed_dev_data.sh   # first time only
./scripts/seed_dev_data.sh
```

This creates:

| Item | Details |
|------|---------|
| **Branches** | Lisbonbranch, portobranch, vilarealbranch |
| **Branch users** | `admin.lisbon@…`, `admin.porto@…`, `admin.vilareal@…` — **branch admin** role in their branch |
| **Warehouse users** | `warehouse.admin@…` / `warehouse.manager@…` / `warehouse.operator@…` — groups `warehouse_admins`, `warehouse_managers`, `warehouse_data_operators` |
| **Items** | ~50 sample items via `products/services.py` |
| **Password** | `devpass123` for all seeded users (override with `--password`) |

Re-running the script is safe (idempotent). Options: `--skip-items`, `--skip-warehouse`.

**Important:** branch **admin** role is for future **order** permissions per branch. **Catalogue** access is the warehouse groups above, not Django admin.

**Manual seed (via `/admin/`)** — if you prefer to practice admin UI:

Start the dev server:

```bash
python manage.py runserver
```

Open `http://localhost:8000/admin/` and log in with the superuser.

Create records in this order:

| Step | Admin model | What to do |
|------|-------------|------------|
| 1 | **Branches** | Add 2–3 branches (e.g. Lisbon, Porto) |
| 2 | **Users** | Add branch users (email + password) — separate from superuser for realistic testing |
| 3 | **Branch memberships** | Link each user to a branch with a role (admin, manager, or user) |

**Notes:**

- A user with **no** branch membership can log in but sees the “no branch access” page.
- To test the branch picker, give **one user** memberships in **two** branches.

### 6. Add sample products

Items are managed in **`/manage/items/`** by warehouse users (Django groups), or created by the seed script / CLI:

```bash
./scripts/seed_dev_data.sh          # recommended — includes 3 products
python manage.py add_product "Cement 50kg" 100 12.95
```

### 7. Test the application

1. Open `http://localhost:8000/` — you should be redirected to login.
2. Log in as a **branch user** (with at least one membership).
3. One branch → catalogue loads. Multiple branches → branch picker, then catalogue.
4. API (same browser session): `http://localhost:8000/api/products/`

Use **one hostname** consistently (`localhost` **or** `127.0.0.1`, not both) — Service Workers are origin-specific.

### 8. Logging

Application logs are written automatically to `logs/` (gitignored) when the server runs:

| File | Logger name |
|------|-------------|
| `logs/centcompras.log` | General |
| `logs/accounts.log` | `centcompras.accounts` |
| `logs/branches.log` | `centcompras.branches` |
| `logs/products.log` | `centcompras.products` |
| `logs/django.log` | `centcompras.django` (HTTP requests) |

In Python code:

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

First-time or reset DB: steps 1–4 above, then `./scripts/seed_dev_data.sh`.

Practice logins (after seed): `warehouse@centcompras.dev` (catalog admin), `admin.lisbon@centcompras.dev` (branch catalogue), password `devpass123`.

---

## Architecture (current)

```text
PostgreSQL
    ↑
User, Item, FamilyProduct, Supplier, SupplierItemPrice, PurchaseOrder(+lines)
    ↑
services.py / permissions.py   (all mutations)
    ↑
views (login required) → API + HTML (item console, PO console)
```

---

## Further reading

- **Start here:** [`docs/handoff.md`](docs/handoff.md) — condensed state + locked decisions + next task
- [`docs/project-plan-2026-08-20.md`](docs/project-plan-2026-08-20.md) — phased plan + status tracker
- [`docs/code-review-2026-08-20.md`](docs/code-review-2026-08-20.md) · [`docs/code-review-audit.md`](docs/code-review-audit.md) — code reviews
- [`docs/user-manual.md`](docs/user-manual.md) — user manual (item console)
- [`docs/user-manual-purchase-orders.md`](docs/user-manual-purchase-orders.md) — user manual (purchase orders)
- [`products/README.md`](products/README.md) — **historical** catalogue build log
- [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — tenancy design; **§6–7 Order is a sketch, NOT to implement**
- [`AGENTS.md`](AGENTS.md) — agent instructions
- [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — development pace

---

## What is explicitly not built yet

The following do **not** exist today. The [Project status](#project-status-handoff) table above is the canonical handoff reference.

### Business features

- **Goods receipt + stock ledger** (Phase 3, next) — recording received goods writes stock
- Stock as a movement ledger (no stock exists yet)
- `orders` app — create, list, edit, delete orders (after inbound stock)
- Shopping cart
- Customers
- Offline order queue in IndexedDB
- Order synchronization when connectivity returns
- Idempotent order submission (client-side order IDs on retry)
- Stock reservation or conflict handling
- Product creation or editing from branch phone UI or public web forms
- In-app branch switcher (only login-time picker for multi-branch users)
- Shared visual chrome on login / branch picker / branch catalogue
- Branch phone-catalogue UX beyond the current scaffold table

### Auth & production

- Google OAuth (production login — dev uses email + password)
- Public signup
- Password reset flow

### Quality & operations

- **Unit tests** — `products`, `procurement`, `accounts` suites green (~156 tests); integration tests not started
- **Integration tests** — not started
- Production deployment and HTTPS
- PWA manifest / install prompt

### Planned next major phase

**Goods receipt + stock ledger (Phase 3):** recording goods received against an approved PO writes stock; stock becomes a movement ledger. Branch **ordering** comes after that, so orders are not placed against zero stock.

Ordering (later): branch users create orders online or queue them offline, then sync to the central warehouse with duplicate-safe retries. Builds on the future `branches` app (Branch, BranchMembership, permissions, `request.active_branch`). Do not implement the `item_name` Order stub in the tenancy doc.
