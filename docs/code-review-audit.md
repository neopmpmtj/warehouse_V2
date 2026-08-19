# CentCompras — Code Review & Audit (report only)

> Read-only audit. **No code was changed.** Backend and frontend reviewed separately.
> Project: `/home/pmpmt/python/260819-central_de_compras/warehouse_V2/`

---

## Test results (run by subagent)

- **90 tests, 0 failures, 0 errors, 0 skipped** — `manage.py test` (accounts 11 + products 79), 377s, exit 0.
- "System check identified no issues (0 silenced)"; no deprecation warnings.
- The `Bad Request / Forbidden` log lines are from tests that intentionally exercise 400/403 paths — expected, not failures.
- ⚠️ Caveat: the Django test client **disables CSRF and runs single-threaded**, so these tests do **not** exercise browser CSRF, concurrency, or race conditions. That's where the manual findings below focus.

---

## BACKEND

### ✅ Done well

- **`select_for_update()`** on every update/deactivate/reactivate path (`services.py`) — prevents lost updates.
- **`@transaction.atomic`** on all create/update mutations — partial-write safety for the single-row paths.
- **DB-level uniqueness constraints** (not just app checks) on internal_code, family name, supplier name — the real concurrency guard.
- **`select_related`** used consistently (`get_items`, history queries) — no N+1 on the hot paths.
- Clean layering: views/CLI/admin all funnel through `services.py`; audit logging is a side-effect of the same transaction.

### 🔴 High — fix to avoid real runtime failures

**1. Bulk operations are not atomic (partial-application risk).**
`console_views.manage_item_bulk` and the admin `deactivate_items` / `reactivate_items` actions loop over items calling `deactivate_item(...)` / `reactivate_item(...)`. Each of those is its **own** `@transaction.atomic`. If iteration #5 raises, items #1–4 are already committed → the DB is left in a half-applied state while the client gets an error. *Fix: wrap the whole loop in one `transaction.atomic` block.*

**2. No server-side max-length validation → raw DB `DataError` (500).**
`services.create_item` / `update_item` / family / supplier never call `full_clean()`. The console HTML has `maxlength`, but that's client-side only. A >255-char `description` or >64-char `internal_code` (or an oversized `reorder_level` exceeding `max_digits=12`) bypasses Django and hits PostgreSQL, which raises `django.db.utils.DataError` → **unhandled 500** instead of a clean 400. *Fix: enforce lengths server-side (call `full_clean()` or validate in services) and map `DataError`/`IntegrityError` to 400s.*

**3. Fragile `IntegrityError` string-matching on create.**
The create paths do check-then-insert; the only thing saving them from a duplicate race is the DB constraint, surfaced via `_save_item`/`_save_family`/`_save_supplier` doing `if "unique_..._ci" in str(exc)`. This works today only because the constraint names happen to be substrings of PostgreSQL's message. If a constraint is ever renamed (or a different backend is used), the match silently misses and a duplicate becomes a raw 500. *Fix: reference the constraint name via a constant / `exc.__cause__`, or use `get_or_create`-style semantics — don't string-scan exception text.*

### 🟡 Medium

**4. Inconsistent uniqueness semantics.** `internal_code` is case-sensitive (plain `UniqueConstraint`), while family and supplier names are case-insensitive (`Lower(name)`). So `"ABC"` and `"abc"` are both valid item codes — likely unintended near-duplicates. *Fix: decide one rule and apply it consistently (probably `Lower("internal_code")`).*

**5. `_lifecycle` has dead code.** `except json.JSONDecodeError` is unreachable because `_parse_json` already converts `JSONDecodeError` into `ValidationError`. Harmless but misleading.

**6. Global monkeypatch.** `accounts.groups.restrict_admin_to_superusers()` overwrites `AdminSite.has_permission` for **all** admin sites at app-import time. It works, but it's a silent global side effect that would clobber any future admin customization. *Fix: use a subclassed `AdminSite` or `ModelAdmin.has_*` overrides instead.*

**7. Group sync runs too eagerly.** `ensure_warehouse_groups` fires on **every** `post_migrate` (and `assign_warehouse_group` calls `sync_warehouse_groups()` on every seed user). Each call deletes the legacy `"Warehouse"` group and re-`set()`s all permissions — which would silently wipe any manual permission tuning. *Fix: make it idempotent-no-op when nothing changed, and drop the per-user re-sync.*

**8. No pagination on the console payload.** `_console_payload`/`get_items` load **every** item into one response and the browser renders all rows. Fine at ~50 rows; degrades badly at thousands. Not a correctness bug, but a scaling one.

**9. Logging not multi-process-safe.** `RotatingFileHandler` is known to lose/corrupt lines under multi-process WSGI (gunicorn). Dev-only for now; flag it before any multi-worker deployment.

**10. Dev credentials in `config/settings.py`** — plaintext PostgreSQL password + `SECRET_KEY = "change-me-in-production"` + `DEBUG = True`. Gitignored, fine for dev, but should move to env vars per the project's own convention before anything leaves localhost.

---

## FRONTEND

### ✅ Done well

- **No XSS surface**: `console.js` renders exclusively via `textContent`/`createElement` — zero `innerHTML`/`document.write` (verified by scan). Strong.
- **Defense-in-depth permissions**: server template sets `data-can-*` flags **and** the API re-checks per action; UI hides/renames controls accordingly.
- **CSRF token is correct** — empirically rendered the template and confirmed `{{ csrf_token }}` resolves to a real token (Django 6 auto-includes the csrf context processor), so browser writes won't 403.
- Good a11y basics (`aria-sort`, `aria-label`, focus handling) and i18n (`en`/`pt-PT`).

### 🔴 High

**11. Double-submit race on Save.** `saveItem()` is `async` but never disables the submit button or sets an in-flight flag. A rapid double-click fires two requests: on **create** this produces **two items** (duplicate rows + two audit logs). *Fix: disable `#item-save` (and the lifecycle/bulk buttons) for the duration of the await, re-enable in `finally`.*

### 🟡 Medium

**12. Item history load race.** `loadHistory(itemId)` writes to the shared `#history-list` with **no** request-id guard — unlike the family/supplier history functions, which correctly use `familyHistoryRequestId`/`supplierHistoryRequestId`. Rapidly switching between items can briefly show the wrong item's history. *Fix: apply the same request-id guard to `loadHistory`.*

**13. Bulk silently skips hidden-but-selected rows.** `applyBulk` derives its ID list from `filteredItems()` ∩ `selectedIds`. If a user selects rows, changes a filter, then applies bulk, the now-hidden selected rows are **silently excluded**. *Fix: act on `state.selectedIds` directly, or warn when selection contains filtered-out rows.*

**14. Offline catalogue is parked/stale.** The served `/service-worker.js` is an **uninstall stub** (it unregisters itself), and `dashboard.html` also unregisters all SWs. The real offline code sits in `products/offline_reference/`, but `product_list.js` calls `/api/items/` (route doesn't exist) and reads `item.stock` (field doesn't exist). So "offline catalogue" is currently **disabled and would be broken if re-enabled**. *Fix: either delete the stale reference or reconcile it with the real `/api/manage/items/` schema before re-enabling.*

### 🟢 Minor

- `currentLang()` / `currentTheme()` read `localStorage` directly — throws in privacy/blocked-storage contexts during `init()`.
- Server-side length limits are absent (see backend #2) — the HTML `maxlength` is the only guard.

---

## Bottom line

The codebase is **well-architected and disciplined** (service layer, transactions, row locking, audit-by-design, no XSS). The tests are green but don't cover the failure modes that actually matter. The highest-value changes, in order: **atomic bulk ops (#1)**, **server-side validation/`full_clean` + `DataError` handling (#2)**, **robust duplicate handling (#3)**, and **frontend double-submit guard (#11)**. Everything else is hardening.
