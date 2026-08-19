# CentCompras — Code Review & Audit (report only)

> Read-only audit. **No code was changed.** Backend and frontend reviewed separately.
> Project: `/home/pmpmt/python/260819-central_de_compras/warehouse_V2/`

---

## 📌 Fix status (updated after Phase 1)

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1 — critical** | #1, #2, #3, #11 | ✅ **DONE** (implemented + tested, full suite green) |
| **Phase 2 — medium** | #4, #5, #6, #7, #12, #13, #14 | ⏳ pending — awaiting go-ahead |
| **Phase 3 — remaining** | #8, #9, #10, #15 (+ cleanup) | ⏳ pending |

Each item below is tagged with its current status.

---

## Test results

- **Baseline (pre-fix):** 90 tests, 0 failures, 0 errors — `manage.py test` (accounts + products).
- **After Phase 1:** **101 tests, 0 failures, 0 errors** — `Ran 101 tests in 226s — OK` (10 new tests added; see changelog).
- "System check identified no issues (0 silenced)"; no deprecation warnings.
- ⚠️ Caveat: the Django test client **disables CSRF and runs single-threaded**, so these tests do **not** exercise browser CSRF, concurrency, or race conditions. The Phase 1 tests simulate concurrency/rollback manually via `mock.patch`.

---

## BACKEND

### ✅ Done well

- **`select_for_update()`** on every update/deactivate/reactivate path (`services.py`) — prevents lost updates.
- **`@transaction.atomic`** on all create/update mutations — partial-write safety for the single-row paths.
- **DB-level uniqueness constraints** (not just app checks) on internal_code, family name, supplier name — the real concurrency guard.
- **`select_related`** used consistently (`get_items`, history queries) — no N+1 on the hot paths.
- Clean layering: views/CLI/admin all funnel through `services.py`; audit logging is a side-effect of the same transaction.

### 🔴 High

**1. Bulk operations are not atomic (partial-application risk).** — ✅ **FIXED (Phase 1)**
`console_views.manage_item_bulk` and the admin `deactivate_items` / `reactivate_items` actions looped over items calling `deactivate_item(...)` / `reactivate_item(...)` — each its own transaction, so a mid-loop failure left partial state. *Fixed: added `bulk_deactivate_items` / `bulk_reactivate_items` in `services.py` (single `@transaction.atomic`) and wired the view + admin actions to them.*

**2. No server-side max-length validation → raw DB `DataError` (500).** — ✅ **FIXED (Phase 1)**
`services.*` never called `full_clean()`; overlong strings / oversized decimals hit PostgreSQL and returned an unhandled 500. *Fixed: `_save_item` / `_save_family` / `_save_supplier` now run `full_clean(validate_unique=False, validate_constraints=False)` before save, and map `DataError` → `ValidationError` (400).*

**3. Fragile `IntegrityError` string-matching on create.** — ✅ **FIXED (Phase 1)**
Duplicate detection relied on `"unique_..._ci" in str(exc)`. *Fixed: `_save_*` now re-runs `validate_*_available(...)` on `IntegrityError`; each save is wrapped in its own `transaction.atomic()` savepoint so the re-check query runs in an un-aborted transaction.*

### 🟡 Medium

**4. Inconsistent uniqueness semantics.** — ⏳ **Phase 2**
`internal_code` is case-sensitive (plain `UniqueConstraint`), while family and supplier names are case-insensitive (`Lower(name)`). So `"ABC"` and `"abc"` are both valid item codes.

**5. `_lifecycle` has dead code.** — ⏳ **Phase 2**
`except json.JSONDecodeError` is unreachable because `_parse_json` already converts `JSONDecodeError` into `ValidationError`.

**6. Global monkeypatch.** — ⏳ **Phase 2**
`accounts.groups.restrict_admin_to_superusers()` overwrites `AdminSite.has_permission` for **all** admin sites at app-import time.

**7. Group sync runs too eagerly.** — ⏳ **Phase 2**
`ensure_warehouse_groups` fires on **every** `post_migrate` (and `assign_warehouse_group` calls `sync_warehouse_groups()` per seed user), deleting the legacy group and re-`set()`ing permissions each time.

**8. No pagination on the console payload.** — ⏳ **Phase 3**
`_console_payload`/`get_items` load **every** item into one response.

**9. Logging not multi-process-safe.** — ⏳ **Phase 3**
`RotatingFileHandler` loses/corrupts lines under multi-process WSGI (gunicorn).

**10. Dev credentials in `config/settings.py`.** — ⏳ **Phase 3**
Plaintext PostgreSQL password + `SECRET_KEY = "change-me-in-production"` + `DEBUG = True`. Gitignored; move to env vars before anything leaves localhost.

---

## FRONTEND

### ✅ Done well

- **No XSS surface**: `console.js` renders exclusively via `textContent`/`createElement` — zero `innerHTML`/`document.write` (verified by scan).
- **Defense-in-depth permissions**: server template sets `data-can-*` flags **and** the API re-checks per action.
- **CSRF token is correct** — empirically rendered the template and confirmed `{{ csrf_token }}` resolves to a real token.
- Good a11y basics (`aria-sort`, `aria-label`, focus handling) and i18n (`en`/`pt-PT`).

### 🔴 High

**11. Double-submit race on Save.** — ✅ **FIXED (Phase 1)**
`saveItem()` was `async` with no in-flight guard → rapid double-click fired duplicate requests (two items on create). *Fixed: added a `state.busy` guard + button disabling across all async mutation entry points (`saveItem`, `applyBulk`, `toggleLifecycle`, `toggleFamilyActive`, `toggleSupplierActive`, `promptCreateFamily`, `createFamilyFromItemForm`, `promptSupplierForm`), reset in `finally`. No automated JS tests (per instruction); `node --check` passes.*

### 🟡 Medium

**12. Item history load race.** — ⏳ **Phase 2**
`loadHistory(itemId)` writes to the shared `#history-list` with no request-id guard (family/supplier history already use request-id guards).

**13. Bulk silently skips hidden-but-selected rows.** — ⏳ **Phase 2**
`applyBulk` derives its ID list from `filteredItems()` ∩ `selectedIds`; hidden-but-selected rows are silently excluded.

**14. Offline catalogue is parked/stale.** — ⏳ **Phase 2**
The served `/service-worker.js` is an uninstall stub; `offline_reference/` hits `/api/items/` and reads `item.stock`, neither of which exists.

### 🟢 Minor

- `currentLang()` / `currentTheme()` read `localStorage` directly — throws in privacy/blocked-storage contexts. — ⏳ **Phase 3**
- ~~Server-side length limits are absent (see backend #2).~~ — ✅ **Resolved by #2 (Phase 1).**

---

## Phase 1 — changes applied (changelog, for resuming later)

### #1 Atomic bulk operations
- `products/services.py` — added `bulk_deactivate_items(user, items, reason="")` and `bulk_reactivate_items(user, items, reason="")`, both `@transaction.atomic`.
- `products/console_views.py` — `manage_item_bulk` calls the bulk function; imports updated.
- `products/admin.py` — `deactivate_items` / `reactivate_items` actions call the bulk functions; imports updated.
- Tests — `BulkLifecycleAtomicityTests` (2): happy path + rollback-on-mid-failure (via `mock.patch`).

### #2 Server-side validation + DataError → 400
- `products/services.py` — `_save_item` / `_save_family` / `_save_supplier` call `full_clean(exclude=None, validate_unique=False, validate_constraints=False)` before save; `DataError` mapped to `ValidationError`; added `from django.db import DataError`.
- Tests — `ServiceValidationTests` (5): overlong description, overlong internal_code, reorder-level overflow, overlong family name, overlong supplier name.

### #3 Robust duplicate handling
- `products/services.py` — `_save_*` catch `IntegrityError` and re-run `validate_internal_code_available` / `validate_family_name_available` / `validate_supplier_name_available` (with `exclude_*_id=item.pk`); each save wrapped in `with transaction.atomic():` so the post-error re-check runs in an un-aborted transaction. Removed the old string-matching logic.
- Tests — `SaveHelperDuplicateMappingTests` (3): item / family / supplier DB-constraint collision maps to the domain error.

### #11 Frontend double-submit guard
- `products/static/products/js/console.js` — added `busy: false` to `state`, an `isBusy()` helper, early-return + `state.busy = true` + `finally { state.busy = false }` across all async mutating entry points; `#item-save` and `#bulk-apply` also disabled/enabled during flight.
- Tests — none (per instruction); validated with `node --check`.

**Phase 1 test result:** full suite `Ran 101 tests — OK` (0 failures, 0 errors).

---

## Bottom line

The codebase is **well-architected and disciplined** (service layer, transactions, row locking, audit-by-design, no XSS). **Phase 1 (critical) is complete and green.** Remaining: Phase 2 (medium #4, #5, #6, #7, #12, #13, #14) and Phase 3 (remaining #8, #9, #10, #15).
