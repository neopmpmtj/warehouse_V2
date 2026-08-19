# CentCompras — Code Review & Audit (report only)

> Read-only audit. Backend and frontend reviewed separately.
> Project: `/home/pmpmt/python/260819-central_de_compras/warehouse_V2/`

---

## 📌 Fix status (updated after Phase 2)

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1 — critical** | #1, #2, #3, #11 | ✅ **DONE** |
| **Phase 2 — medium** | #4, #5, #6, #7, #12, #13, #14 | ✅ **DONE** |
| **Phase 3 — remaining** | #8, #9, #10, #15 (+ cleanup) | ⏳ pending — awaiting go-ahead |

Each item below is tagged with its current status.

---

## Test results

- **Baseline (pre-fix):** 90 tests, 0 failures, 0 errors.
- **After Phase 1:** 101 tests, 0 failures, 0 errors.
- **After Phase 2:** **104 tests, 0 failures, 0 errors** (`Ran 104 tests in ~247s — OK`).
- "System check identified no issues (0 silenced)"; no deprecation warnings.
- ⚠️ Caveat: the Django test client **disables CSRF and runs single-threaded**, so these tests do **not** exercise browser CSRF, concurrency, or race conditions. Concurrency/rollback is simulated via `mock.patch`.

---

## BACKEND

### ✅ Done well

- **`select_for_update()`** on every update/deactivate/reactivate path (`services.py`) — prevents lost updates.
- **`@transaction.atomic`** on all create/update mutations.
- **DB-level uniqueness constraints** on internal_code, family name, supplier name.
- **`select_related`** used consistently — no N+1 on hot paths.
- Clean layering: views/CLI/admin funnel through `services.py`; audit logging is a side-effect of the same transaction.

### 🔴 High

**1. Bulk operations are not atomic (partial-application risk).** — ✅ **FIXED (Phase 1)**
Added `bulk_deactivate_items` / `bulk_reactivate_items` in `services.py` (single `@transaction.atomic`); wired view + admin actions to them.

**2. No server-side max-length validation → raw DB `DataError` (500).** — ✅ **FIXED (Phase 1)**
`_save_item` / `_save_family` / `_save_supplier` now run `full_clean(validate_unique=False, validate_constraints=False)` before save and map `DataError` → `ValidationError` (400).

**3. Fragile `IntegrityError` string-matching on create.** — ✅ **FIXED (Phase 1)**
`_save_*` re-run `validate_*_available(...)` on `IntegrityError`; save wrapped in its own `transaction.atomic()` savepoint so the re-check runs in an un-aborted transaction.

### 🟡 Medium

**4. Inconsistent uniqueness semantics.** — ✅ **FIXED (Phase 2)**
`internal_code` uniqueness is now case-insensitive: `UniqueConstraint(Lower("internal_code"), condition=~Q(internal_code=""), name="unique_item_internal_code_ci")` (migration `0003_item_internal_code_ci`); `validate_internal_code_available` uses `internal_code__iexact`; `seed_dev_data` lookup uses `__iexact`.

**5. `_lifecycle` has dead code.** — ✅ **FIXED (Phase 2)**
Removed the unreachable `except json.JSONDecodeError` branch in `console_views.py`.

**6. Global monkeypatch.** — ✅ **FIXED (Phase 2)**
Replaced `restrict_admin_to_superusers()` (which patched `AdminSite.has_permission` globally) with a proper `SuperuserAdminSite(AdminSite)` wired via `AdminConfig.default_site` (`accounts.admin_site.CentComprasAdminConfig`). Removed the monkeypatch from `groups.py` and its call in `apps.py`.

**7. Group sync runs too eagerly.** — ✅ **FIXED (Phase 2)**
`sync_warehouse_groups()` is now idempotent (only `permissions.set()` when the set actually differs; no recurring legacy-group delete); `assign_warehouse_group()` no longer re-syncs on every call.

**8. No pagination on the console payload.** — ⏳ **Phase 3**
`_console_payload`/`get_items` load **every** item into one response.

**9. Logging not multi-process-safe.** — ⏳ **Phase 3**
`RotatingFileHandler` loses/corrupts lines under multi-process WSGI (gunicorn).

**10. Dev credentials in `config/settings.py`.** — ⏳ **Phase 3**
Plaintext PostgreSQL password + `SECRET_KEY = "change-me-in-production"` + `DEBUG = True`. Move to env vars before anything leaves localhost.

---

## FRONTEND

### ✅ Done well

- **No XSS surface**: `console.js` renders via `textContent`/`createElement` only — zero `innerHTML` (verified by scan).
- **Defense-in-depth permissions**: server template sets `data-can-*` flags **and** the API re-checks per action.
- **CSRF token is correct** (verified by rendering the template).
- Good a11y basics and i18n (`en`/`pt-PT`).

### 🔴 High

**11. Double-submit race on Save.** — ✅ **FIXED (Phase 1)**
Added a `state.busy` in-flight guard + button disabling across all async mutation entry points (`saveItem`, `applyBulk`, `toggleLifecycle`, `toggleFamilyActive`, `toggleSupplierActive`, `promptCreateFamily`, `createFamilyFromItemForm`, `promptSupplierForm`), reset in `finally`. No automated JS tests (per instruction); `node --check` passes.

### 🟡 Medium

**12. Item history load race.** — ✅ **FIXED (Phase 2)**
Added an `itemHistoryRequestId` request-id guard to `loadHistory()`, matching the existing family/supplier guards.

**13. Bulk silently skips hidden-but-selected rows.** — ✅ **FIXED (Phase 2)**
`applyBulk()` now sends `[...state.selectedIds].sort(...)` (the full selection) instead of `filteredItems() ∩ selectedIds`.

**14. Offline catalogue is parked/stale.** — ✅ **FIXED (Phase 2, option "delete")**
Deleted `products/offline_reference/` and the served `service_worker.js` stub; removed the `service_worker` view, the `/service-worker.js` route, and the dashboard's unregister `<script>` + link. (Docs still reference offline in places — see note below.)

### 🟢 Minor

- `currentLang()` / `currentTheme()` read `localStorage` directly — throws in privacy/blocked-storage contexts. — ⏳ **Phase 3**
- ~~Server-side length limits are absent (see backend #2).~~ — ✅ **Resolved by #2 (Phase 1).**

---

## Phase 1 — changes applied (changelog)

### #1 Atomic bulk operations
- `products/services.py` — added `bulk_deactivate_items(user, items, reason="")` and `bulk_reactivate_items(...)`, both `@transaction.atomic`.
- `products/console_views.py` — `manage_item_bulk` calls the bulk function.
- `products/admin.py` — `deactivate_items` / `reactivate_items` actions call the bulk functions.
- Tests — `BulkLifecycleAtomicityTests` (2): happy path + rollback-on-mid-failure.

### #2 Server-side validation + DataError → 400
- `products/services.py` — `_save_*` run `full_clean(validate_unique=False, validate_constraints=False)` before save; `DataError` mapped to `ValidationError`; imported `DataError`.
- Tests — `ServiceValidationTests` (5).

### #3 Robust duplicate handling
- `products/services.py` — `_save_*` catch `IntegrityError` and re-run `validate_*_available(...)`; save wrapped in `with transaction.atomic():`.
- Tests — `SaveHelperDuplicateMappingTests` (3).

### #11 Frontend double-submit guard
- `products/static/products/js/console.js` — `state.busy` guard + button disabling across all async mutations.
- Tests — none (per instruction); `node --check` passes.

---

## Phase 2 — changes applied (changelog)

### #4 Case-insensitive internal_code
- `products/models.py` — constraint → `Lower("internal_code")` (name `unique_item_internal_code_ci`).
- `products/services.py` — `validate_internal_code_available` uses `internal_code__iexact`.
- `products/management/commands/seed_dev_data.py` — idempotency lookup uses `__iexact`.
- `products/migrations/0003_item_internal_code_ci.py` — new migration (verified: dev DB has 61 items, no case-duplicates).
- Test — `ItemServiceTests.test_duplicate_internal_code_is_case_insensitive`.

### #5 Dead code
- `products/console_views.py` — removed unreachable `except json.JSONDecodeError` in `_lifecycle`.

### #6 Custom admin site
- `accounts/admin_site.py` (new) — `SuperuserAdminSite` + `CentComprasAdminConfig` (`default_site`).
- `accounts/apps.py` — removed `restrict_admin_to_superusers()` call; `AccountsConfig` no longer imports AdminConfig.
- `accounts/groups.py` — removed `restrict_admin_to_superusers()` and the `AdminSite` import.
- `config/settings.py` + `config/settings.example.py` — `django.contrib.admin` → `accounts.admin_site.CentComprasAdminConfig`.
- Covered by existing `DjangoAdminAccessTests` / `ItemAdminAccessTests` / etc.

### #7 Idempotent group sync
- `accounts/groups.py` — `sync_warehouse_groups()` idempotent (only `set()` when changed; no recurring legacy delete); `assign_warehouse_group()` no longer calls sync.
- Tests — `WarehouseGroupTests.test_sync_warehouse_groups_is_idempotent`, `test_assign_warehouse_group_preserves_extra_permission`.

### #12 Item history guard
- `products/static/products/js/console.js` — `itemHistoryRequestId` guard in `loadHistory()`.

### #13 Bulk acts on full selection
- `products/static/products/js/console.js` — `applyBulk()` uses `[...state.selectedIds].sort((a,b)=>a-b)`.

### #14 Offline catalogue removal
- Deleted `products/offline_reference/` (5 files) and `products/templates/products/service_worker.js`.
- `products/views.py` — removed `service_worker` view.
- `products/web_urls.py` — removed `service-worker.js` route.
- `products/templates/products/dashboard.html` — removed the `/service-worker.js` link and the SW-unregister `<script>`.

**Phase 2 test result:** full suite `Ran 104 tests — OK` (0 failures, 0 errors).

---

## Bottom line

The codebase is **well-architected and disciplined** (service layer, transactions, row locking, audit-by-design, no XSS). **Phase 1 (critical) and Phase 2 (medium) are complete and green.** Remaining: Phase 3 (#8 pagination, #9 multi-process logging, #10 dev credentials, #15 localStorage guard).

> ⚠️ Note: `README.md`, `products/README.md`, and `products/products_docs/aux_instructions.md` still describe the now-removed offline catalogue (offline_reference, `/service-worker.js`, `/api/items/`). Consider a separate doc-cleanup pass before relying on those docs.
