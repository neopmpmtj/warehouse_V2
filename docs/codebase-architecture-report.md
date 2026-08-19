# CentCompras — Codebase Architecture & Tech Stack Report

> Read-only exploration. No data, only architecture and tech stack.
> Generated for `/home/pmpmt/python/260819-central_de_compras/warehouse_V2/`

---

## 1. Size

| Dimension | Count |
|---|---|
| Python source lines (project only) | **4,677** across ~29 modules |
| Frontend lines (JS/HTML/CSS, project only) | **~2,600** (console.js alone is 1,166) |
| Django apps | **3** (`accounts`, `products`, `logging_utils`) + `config` project package |
| Python modules | **~29** (excl. `.venv`, `__init__.py`, and 2 migrations) |
| Functions/methods/classes defined | **~150** (see §4) |
| Test code | **1,240 lines** (accounts 157 + products 1,083) |
| Migrations | 3 (accounts 1, products 2) |

**Verdict:** a **small-to-mid MVP**. The real logic lives in a handful of files
(`products/services.py`, `products/console_views.py`, `products/admin.py`, `products/tests.py`).

---

## 2. Tech stack

- **Language/runtime:** Python 3.12.3
- **Framework:** Django **6.1**
- **Database:** PostgreSQL via `psycopg` **3.3.4** (`psycopg[binary]`)
- **Frontend:** Plain Django templates + **vanilla JavaScript** (no React/Vue),
  a single-page-style staff console in `console.js`, i18n via `console_i18n.js`
- **Offline:** Service Worker + IndexedDB (read-only catalogue cache)
- **Auth:** Custom `User` (email login), Django groups + model permissions
- **Logging:** Custom `logging_utils` package (rotating file handlers → `logs/`)
- **Deps:** only `Django` + `psycopg` (requirements.txt is 2 lines)

---

## 3. Module inventory (by app)

### `config/` (project)
`settings.py`, `urls.py`, `asgi.py`, `wsgi.py` — pure boilerplate, **0 functions**.
Routes: `/admin/`, `/accounts/`, `/api/` (products console API), `/` (web URLs).

### `accounts/` — auth & roles
- `models.py` — `UserManager`, `User` (email-as-username, `AbstractBaseUser`)
- `groups.py` — warehouse group sync (admins/managers/operators)
- `admin.py`, `views.py` (custom `LoginView`), `urls.py`, `tests.py`

### `products/` — the core catalogue app
- `models.py` — catalogue models (`Item`, `FamilyProduct`, `Supplier`, `VatRate`, 3 change-log models)
- `services.py` — **business-logic layer** (all mutations + validation)
- `console_views.py` — JSON API for the staff console
- `admin.py` — Django admin (superuser-only, lifecycle audit actions)
- `permissions.py`, `views.py` (dashboard + service worker), `urls.py`, `web_urls.py`
- `management/commands/` — `add_item`, `seed_dev_data`
- `seed_catalog_data.py` — data literals (no functions)
- `offline_reference/` — SW + IndexedDB reference impl; `static/` + `templates/`

### `logging_utils/`
`logging_config.py` (6 functions), `apps.py`, `__init__.py` (re-exports `get_logger`).

---

## 4. Function inventory by module

### `accounts/groups.py` (6 + 1 nested)
`_codenames_for_group`, `_products_permissions`, `sync_warehouse_groups`,
`ensure_warehouse_groups`, `clear_permission_cache`, `assign_warehouse_group`,
`restrict_admin_to_superusers` (nested `has_permission`)

### `accounts/models.py` (2 classes, 4 methods)
`UserManager` (`_create_user`, `create_user`, `create_superuser`), `User` (`__str__`)

### `accounts/admin.py` — `UserAdmin` (1)

### `accounts/views.py` — `LoginView` (1)

### `accounts/tests.py` (4 classes, 13 tests)
`UserModelTests`, `WarehouseGroupTests`, `LoginViewTests`, `DjangoAdminAccessTests`

### `logging_utils/logging_config.py` (6)
`get_project_base_dir`, `determine_log_dir`, `create_rotating_file_handler`,
`set_console_level`, `get_logger`, `configure_django_loggers`

### `manage.py` — `main` (1)

### `products/models.py` (8 model classes)
`VatRate`, `FamilyProduct`, `ItemQuerySet` (`active`), `Item`, `Supplier`,
`ItemChangeLog`, `FamilyChangeLog`, `SupplierChangeLog`

### `products/services.py` (8 error classes + 31 functions — the core layer)

**Errors:** `DuplicateInternalCodeError`, `DeactivateReasonRequiredError`,
`ReactivateReasonRequiredError`, `FamilyNameRequiredError`, `DuplicateFamilyNameError`,
`SupplierNameRequiredError`, `DuplicateSupplierNameError`, `InvalidSupplierEmailError`

**Helpers:** `_serialize_value`, `_normalize_internal_code`,
`validate_internal_code_available`, `_resolve_family`, `_resolve_vat_rate`,
`_log_item_change`, `_save_item`, `_action_for_field_changes`, `_normalize_family_name`,
`validate_family_name_available`, `_save_family`, `_log_family_change`,
`_normalize_supplier_name`, `validate_supplier_name_available`, `_normalize_supplier_email`,
`_save_supplier`, `_log_supplier_change`

**Item ops:** `create_item`, `update_item`, `deactivate_item`, `reactivate_item`,
`get_items`, `get_item_history`, `get_vat_rates`

**Family ops:** `create_product_family`, `update_product_family`, `get_family_history`,
`get_product_families`

**Supplier ops:** `create_supplier`, `update_supplier`, `get_suppliers`

### `products/console_views.py` (27 functions — JSON API)
`_json_error`, `_parse_json`, `_decimal_string`, `_serialize_vat_rate`, `_serialize_family`,
`_serialize_item`, `_serialize_history_entry`, `_unit_choices`, `_console_payload`,
`_parse_decimal`, `_parse_unit`, `_families_with_counts`, `_get_family`, `_family_response`,
`_get_item`, `_item_response`, `item_console`, `manage_item_list`, `manage_item_detail`,
`manage_item_deactivate`, `manage_item_reactivate`, `_lifecycle`, `manage_item_bulk`,
`manage_item_history`, `_family_error`, `manage_family_list`, `manage_family_detail`,
`manage_family_history`

### `products/admin.py` (~19 classes / ~50 methods)
`ItemAdminForm`, `ItemChangeLogInline`, `FamilyChangeLogInline`, `SupplierChangeLogInline`,
`ItemAdmin` (9 methods incl. `deactivate_items`/`reactivate_items`/`_lifecycle_reason_page`),
`SupplierAdminForm`, `SupplierAdmin`, `FamilyProductItemInline`, `FamilyProductAdminForm`,
`FamilyProductAdmin`, `_ReadOnlyChangeLogAdmin`, `ItemChangeLogAdmin`,
`FamilyChangeLogAdmin`, `SupplierChangeLogAdmin`, `VatRateAdmin`

### `products/permissions.py` (4)
`can_view_catalog`, `can_manage_catalog`, `deny_unless`, `catalog_required`
(decorator, nested `wrapped`)

### `products/views.py` (2)
`staff_dashboard`, `service_worker`

### `products/management/commands/add_item.py` + `seed_dev_data.py`
(1 class each: `Command` with `add_arguments`, `handle`)

### `products/tests.py` (~60 tests + 1 helper)
`make_warehouse_user` helper + test classes: `ItemTestCaseMixin`, `ItemServiceTests`,
`FamilyProductServiceTests`, `ItemPermissionTests`, `ItemAdminAccessTests`,
`FamilyProductAdminAccessTests`, `SupplierServiceTests`, `SupplierAdminAccessTests`,
`ItemConsoleTests`

---

## 5. Architecture (how it's wired)

```
Browser/console.js  →  console_views.py (JSON API)  →  services.py  →  models.py  →  PostgreSQL
CLI (add_item)      →  services.py (same path, audit user = null)
Django admin        →  admin.py → services.py
```

- **Layered:** all business logic centralized in `services.py`; views/CLI/admin never
  touch models directly for mutations.
- **Audit-by-design:** every create/update/deactivate/reactivate writes to `*ChangeLog`
  models with a required lifecycle reason.
- **RBAC:** Django groups (`warehouse_admins`/`managers`/`data_operators`) gate catalogue
  mutations; `/admin/` is superuser-only; branch roles are meant to be read-only.
- **Two frontends:** a staff console SPA (`item_console.html` + `console.js`) and an
  offline branch catalogue (Service Worker + IndexedDB).
- **URL layout:** `/` dashboard, `/manage/items/` console, `/api/manage/*` JSON endpoints,
  `/accounts/login|logout`, `/admin/`.

---

## ⚠️ Observations

1. **Docs are ahead of the code.** `AGENTS.md` describes a `branches` app (`Branch`,
   `BranchMembership`, `ActiveBranchMiddleware`, branch picker) and a read-only
   `GET /api/products/` catalogue endpoint for branches. **None of that exists in the
   code** — there is no `branches/` directory, no `ActiveBranchMiddleware` in
   `MIDDLEWARE`, and the only API routes are the `api/manage/*` console endpoints.
   The "tenancy" layer is documented but not implemented.

2. **Hardcoded DB credentials.** `config/settings.py` contains a plaintext PostgreSQL
   password. It is gitignored (per AGENTS.md), but per project convention secrets belong
   in `~/.pi/agent/.env`.

3. **Single shared module for the API.** `console_views.py` mixes JSON serialization,
   validation, and ~15 view functions — fine at this size, but it is the file to split
   if the console grows.
