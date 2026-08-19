# CentCompras — Central Warehouse

A Django web application for a company with a **central warehouse** and **satellite branches**. Branch staff browse the product catalogue from a phone browser and will eventually place orders against central stock — including in areas with poor mobile coverage.

This repository is an early-stage MVP built incrementally: one concept per phase, with clear separation of responsibilities and no unnecessary frameworks.

---

## Project status (handoff)

*Last updated: 18 August 2026 — read this section first when resuming work.*

### Where we stand

The **catalogue module is complete** for the current MVP scope: global products, warehouse-staff management with audit trail (products, families, and suppliers), branch read-only browsing (online + offline), and local dev seed data.

**Stock is still a number typed on the product** in `/manage/products/`. Branch **orders** are on hold until inbound stock can be recorded from supplier purchases, so an order is not placed against an empty warehouse. Nothing in `orders/` or a procurement app exists yet.

Held for later dedicated sessions (do not start in passing): shared page chrome, branch phone-catalogue UX, staff-console polish.

### Completed

| Phase | Status | Notes |
|-------|--------|-------|
| **Product catalogue MVP** | Done | Model, API, offline HTML/JS, Service Worker, IndexedDB — see [`products/README.md`](products/README.md) |
| **Auth & tenancy foundation** | Done | `accounts` (email login), `branches` (Branch, BranchMembership, roles, middleware, picker) |
| **Login-protected catalogue** | Done | `/` and `/api/products/` require session; API returns 401 when logged out |
| **Centralized logging** | Done | `logging_utils` → rotating files in `logs/` |
| **Catalog management & audit** | Done | Product / family / supplier lifecycle, `ProductChangeLog` + `FamilyChangeLog` + `SupplierChangeLog`, soft delete, staff admin via `products/services.py` |
| **Catalog polish** | Done | `catalog_updated_at` in API + UI; duplicate `internal_code` validation; optional product audit `reason` |
| **Staff product console** | Done | `/manage/products/` — table, filters, column sort, inactive-by-default create + Genesis, family/supplier drawers, EN/pt-PT, light/dark |
| **Family & supplier priors** | Done | Console create/deactivate; case-insensitive unique names (no rename in the console); PostgreSQL audit logs |
| **Dev seed script** | Done | [`scripts/seed_dev_data.sh`](scripts/seed_dev_data.sh) — branches, branch users, **warehouse user**, sample products |
| **Project setup docs** | Done | Root README, `requirements.txt`, `config/settings.example.py`, `AGENTS.md`, `.cursor/` rules |

**Design choices locked in for later phases:**

- `Product` catalogue is **global** (central warehouse) — no `branch_id` on products.
- **Catalog mutations** = warehouse staff (`is_staff`) only. **Branch roles** = future branch-scoped documents (orders), not catalogue edit.
- Dev login: email + password. Production: **Google OAuth** (not implemented yet).
- Users are provisioned in admin or seed script — no public signup.
- Orders (future, after inbound stock) will be **branch-scoped** with `branch` + `created_by` FKs. The sketch in [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6 is **not** an implementation spec (`item_name` is leftover).
- **`Product.stock` as a console-editable field is not locked.** Inbound receipts from suppliers are expected to become the source of stock quantity.

### User roles (important — practice with these)

| User type | Example (after seed) | Can do today |
|-----------|----------------------|--------------|
| **Warehouse staff** | `warehouse@centcompras.dev` | Add/edit/deactivate products, families, and suppliers in `/manage/products/` (and `/admin/products/`); audit logs. Today they also type **stock** on the product. |
| **Branch admin** | `admin.lisbon@centcompras.dev` | Log in, browse catalogue at `/` (read-only); future: orders in their branch (after inbound stock exists) |
| **Branch manager / user** | (create in admin) | Same browse access; different order permissions later |
| **Django superuser** | from `createsuperuser` | Site admin: users, branches, memberships — not the same as warehouse or branch admin unless you grant `is_staff` / memberships |

After `./scripts/seed_dev_data.sh`, all seeded users share password **`devpass123`**.

### Not started / pending

| Area | Priority | Notes |
|------|----------|-------|
| **Inbound stock / procurement** | **Next (design)** | Warehouse buys from suppliers; a receipt should **write product stock**, not a person typing it on the product row. No app yet — agree the smallest first slice before coding. |
| **Orders workflow** | After inbound stock | Branch requests against central stock. Sketch only: [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) §6–7. Do not implement the stub `item_name` model. |
| **Order business rules** | Before coding orders | Multi-line cart vs single line; stock decrement timing; cancel/edit policy |
| **Shared page chrome** | Later session | Same header/CSS on login, branch picker, `/`, so new pages do not look like a different app |
| **Branch phone catalogue UX** | Later session | Search, family, unit, human stock/price — hold; `/` stays a scaffold until that session |
| **Staff console polish** | Later session | History diffs, default Active filter, Genesis copy — hold |
| **Tests (accounts/branches)** | Later | `accounts/tests.py`, `branches/tests.py` still stubs; `products/tests.py` covers catalogue + console (~86 tests) |
| **Integration tests** | Later | Full auth → branch middleware → catalogue API → offline flow |
| **Google OAuth** | Production | `django-allauth` or similar |
| **Public signup / password reset** | Later | |
| **Branch switcher in catalogue** | Later | Multi-branch users pick at login only; no in-app switch |
| **Production deployment** | Later | HTTPS, env secrets, PWA manifest |
| **Catalog extras (deferred)** | Later | Categories extras, LLM/vector search on `description`, bulk import |

### Recommended next session

1. Read this section, [User roles](#user-roles-important--practice-with-these), and the staff console session reports: [`docs/product-console-session-2026-08-18.md`](docs/product-console-session-2026-08-18.md), [sort + lifecycle](docs/product-console-session-2026-08-18-sort-lifecycle.md), [family + supplier](docs/product-console-session-2026-08-18-family-supplier.md), [family + supplier audit](docs/product-console-session-2026-08-18-family-supplier-audit.md).
2. Fresh environment: `python manage.py migrate` then `./scripts/seed_dev_data.sh`.
3. Practice: warehouse user → `/manage/products/`; create a family if needed; new product starts inactive until Genesis; Families / Suppliers drawers show History. Branch user → `/` catalogue; deactivate a product (reason required) → confirm it disappears from branch API.
4. **Design inbound stock** (procurement / goods receipt): how a supplier purchase becomes `Product.stock`. Do not start `orders/` until stock can be received.
5. Do **not** in passing: restyle `/`, polish the staff console, or implement the tenancy-doc `Order` stub.

### Key files (catalog — current module)

```text
products/models.py           Product, ProductFamily, Supplier, change-log models
products/services.py         create/update/deactivate/reactivate, family/supplier, get_products
products/permissions.py      can_manage_catalog (is_staff)
products/admin.py            staff-only admin + audit inlines
products/views.py              GET /api/products/ (active only + catalog_updated_at)
products/console_views.py      Staff console page + /api/manage/ products, families, suppliers
products/tests.py              Catalog + console tests — run: python manage.py test products
branches/management/commands/seed_dev_data.py
scripts/seed_dev_data.sh       wrapper: migrate + seed
```

Migrations: `products/0001_initial.py` through `0005` (inactive-by-default, CI unique names, family/supplier audit). Run `migrate` after pull if schema changed.

### Development philosophy

One concept per phase. Reusable `services.py` layer. Plain Django + plain JavaScript. Do not dump a finished application in one step. See [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md).

---

## Business scenario

- A central warehouse holds the master product catalogue and stock levels. **Today, stock is typed on the product.** The next product-side work is recording supplier receipts so that quantity is filled from purchases, not from the product form.
- Branch users access a lightweight web app (plain HTML + JavaScript) from their phones. **Branch orders wait** until inbound stock exists.
- Users may travel through areas with little or no mobile data, so the client must work **offline** for catalogue browsing (and, in a future phase, for queuing orders).
- PostgreSQL on the server is the **source of truth**. The browser's IndexedDB is a **read-only local cache** of the last successfully downloaded catalogue.

Warehouse staff manage the catalogue in the staff console at `/manage/products/` (`is_staff` users). Django admin remains available. Branch phone users have **read-only** access via the API and offline cache. The CLI (`add_product`) remains for dev/bootstrap only.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Django 6.1 |
| Database | PostgreSQL (`centcompras_db`) |
| Frontend | Plain HTML, plain JavaScript |
| Offline | Service Worker (app shell), IndexedDB (catalogue data) |
| Logging | `logging_utils` — console + rotating files in `logs/` |

No React, Vue, or similar frontend framework.

---

## What works today

### Authentication and tenancy

- Custom `User` model (`accounts`) — email login, no username field
- Session login/logout at `/accounts/login/` and `/accounts/logout/`
- `Branch` and `BranchMembership` models (`branches`) — roles per branch: Admin, Manager, User
- Active branch stored in session; branch picker when user belongs to multiple branches
- Permission helpers in `branches/permissions.py` (ready for orders)
- Django admin for users, branches, and memberships
- Catalogue requires login; API returns 401 when unauthenticated

Production will use Google OAuth (not implemented in dev — email/password login only).

### Product catalogue (server)

- `Product` model: required `family`, optional `internal_code`, `description`, `stock` (decimal), `price` (USD), `unit_of_measure`, `reorder_level`, `is_active` (soft delete; **new products start inactive**), timestamps.
- `ProductFamily` / `Supplier` — family is required on create; suppliers are optional. Names are case-insensitive unique. Console does not rename them.
- Audit: `ProductChangeLog`, `FamilyChangeLog`, `SupplierChangeLog` — who changed what (create / update / deactivate / reactivate). Product deactivate/reactivate require a reason; family/supplier lifecycle does not.
- Service layer in [`products/services.py`](products/services.py): product, family, and supplier mutations.
- Warehouse staff manage the catalogue in `/manage/products/` (`products/permissions.py` — `is_staff` only). Django admin remains available.
- Dev/bootstrap CLI:

  ```bash
  python manage.py add_product "Cement 50kg" 100 12.95
  python manage.py add_product "Steel Pipe" 50 8.75 --internal-code PIPE-20
  ```

- JSON API (authenticated, **active products only**):

  ```text
  GET /api/products/
  ```

  Response includes `catalog_updated_at` (ISO timestamp of the latest active product change) for offline stale-catalogue messaging.

- `ProductChangeLog.reason` — required for product deactivate/reactivate; optional on field edits. Family/supplier logs store an empty reason today.
- Duplicate non-empty `internal_code` values are rejected with a clear validation error in admin and services.
- Tests in [`products/tests.py`](products/tests.py) cover service diffs, active filtering, uniqueness, console APIs, and audit logs.

### Product catalogue (browser)

- Product list page at `/` (login required).
- Fetches catalogue from the API when online, saves to IndexedDB, renders a table.
- On API failure, falls back to the last cached catalogue in IndexedDB.
- Service Worker caches the application shell so the page and scripts load offline.
- Retries when connectivity returns (`online` event) and every 30 seconds while the app is open.

### URL layout

| Path | Purpose |
|------|---------|
| `/` | Product list page (login required) |
| `/manage/products/` | Warehouse staff product console (`is_staff`) |
| `/api/manage/products/` | Staff product JSON API (`is_staff`) |
| `/api/manage/families/` | Staff family JSON API (`is_staff`) |
| `/api/manage/suppliers/` | Staff supplier JSON API (`is_staff`) |
| `/accounts/login/` | Email + password login |
| `/accounts/logout/` | Log out |
| `/branches/select/` | Choose active branch (multi-branch users) |
| `/branches/no-access/` | Shown when user has no branch membership |
| `/api/products/` | Catalogue JSON API (login required) |
| `/service-worker.js` | Service Worker (served from root for correct scope) |
| `/admin/` | Django admin |

---

## Project structure

```text
warehouse/
├── manage.py
├── requirements.txt
├── config/
│   ├── settings.example.py   # copy to settings.py locally
│   ├── urls.py
│   └── ...
├── accounts/                 # custom User, login/logout
├── branches/                 # Branch, BranchMembership, active branch middleware
├── logging_utils/            # centralized logging (console + logs/)
├── AGENTS.md                 # Cursor agent instructions
├── .cursor/                  # Cursor rules and commands
├── docs/
│   └── warehouse-tenancy-setup.md
└── products/                 # catalogue app
    ├── models.py
    ├── services.py
    ├── views.py
    └── ...
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
| **Warehouse staff** | `warehouse@centcompras.dev` — manages **catalog** in `/manage/products/` (`is_staff`) |
| **Products** | 3 sample items via `products/services.py` |
| **Password** | `devpass123` for all seeded users (override with `--password`) |

Re-running the script is safe (idempotent). Options: `--skip-products`, `--skip-warehouse`.

**Important:** branch **admin** role is for future **order** permissions per branch. **Catalogue** add/edit/deactivate is **warehouse staff only** (`is_staff`), not branch role.

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

Products are managed in **`/manage/products/`** by warehouse staff (`is_staff`), or created by the seed script / CLI:

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
User, Branch, BranchMembership, Product
    ↑
services.py / permissions.py
    ↑
views (login required) → API + HTML
    ↑
product_list.js → IndexedDB

Service Worker → caches HTML + JS (app shell, offline page load)
```

---

## Further reading

- **Start here:** [Project status (handoff)](#project-status-handoff) in this file
- [`docs/product-console-session-2026-08-18.md`](docs/product-console-session-2026-08-18.md) — staff product console: request, stack, decisions, bugs fixed
- [`docs/product-console-session-2026-08-18-sort-lifecycle.md`](docs/product-console-session-2026-08-18-sort-lifecycle.md) — column sort, inactive create, Genesis / activate / deactivate presets
- [`docs/product-console-session-2026-08-18-family-supplier.md`](docs/product-console-session-2026-08-18-family-supplier.md) — family and supplier console priors
- [`docs/product-console-session-2026-08-18-family-supplier-audit.md`](docs/product-console-session-2026-08-18-family-supplier-audit.md) — family/supplier PostgreSQL audit, History in drawers, leftover 1–3
- [`products/README.md`](products/README.md) — **historical** catalogue build log and offline checklist; current facts are in this README’s Project status
- [`docs/warehouse-tenancy-setup.md`](docs/warehouse-tenancy-setup.md) — tenancy design (accounts/branches done); **§6–7** is an Order *sketch*, not the next build; see preamble for inbound stock
- [`AGENTS.md`](AGENTS.md) — concise instructions for AI agents in Cursor
- [`products/products_docs/aux_instructions.md`](products/products_docs/aux_instructions.md) — incremental development pace (status synced August 2026)

---

## What is explicitly not built yet

The following do **not** exist today. The [Project status](#project-status-handoff) table above is the canonical handoff reference.

### Business features

- Inbound stock / procurement app — recording supplier purchases so `Product.stock` is filled from receipts
- Stock as a movement ledger (today stock is still typed on the product)
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

- **Unit tests** — `products/tests.py` covers catalogue and console; `accounts/tests.py` and `branches/tests.py` still stubs
- **Integration tests** — not started
- Production deployment and HTTPS
- PWA manifest / install prompt

### Planned next major phase

**Inbound stock (procurement / goods receipt):** warehouse purchases from suppliers; a data person records the receipt; product stock is updated from that receipt. Branch **ordering** comes after that, so orders are not placed against zero stock.

Ordering (later): branch users create orders online or queue them offline, then sync to the central warehouse with duplicate-safe retries. Builds on existing `Branch`, `BranchMembership`, `permissions.py`, and `request.active_branch`. Do not implement the `item_name` Order stub in the tenancy doc.
