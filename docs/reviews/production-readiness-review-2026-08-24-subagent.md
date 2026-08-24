# Production-Readiness Review — CentCompras (warehouse_V2)

**Date:** 2026-08-24 · **Reviewer:** sub-agent (read-only, independent pass A)
**Scope:** multi-user races · DB connection lifecycle · security · performance · resilience · secrets/config · dependencies · migration safety
**Method:** static read of `accounts, products, procurement, inventory, branches, orders, threads, company_voice, logging_utils, config, deploy`. No tests run, no DB touched, no code modified.

**Verdict:** 🔶 **NEARLY READY** — no Critical findings; the concurrency model is genuinely strong (consistent lock ordering, item-level serialization of stock/reservation writes, branch isolation via 404). Two High deployment/security items and a handful of Medium perf/robustness items stand between this and a clean production cut.

---

## 🔴 Critical

**None found.** The core stock-ledger, FIFO-reservation, PO-approval-snapshot, and branch-receipt paths are correctly wrapped in `transaction.atomic` + `select_for_update`, with a consistent lock order (request/PO → item → line). No lost-update or TOCTOU bug was found on the primary money/stock paths.

---

## 🟠 High

### H1 — SECRET_KEY env-var name mismatch breaks production boot
- **Files:** `config/settings/prod.py:13` (`SECRET_KEY = config("DJANGO_SECRET_KEY")`), `config/settings/dev.py:9-11` (same key, has a dev fallback), vs `.env.example:6` (`# SECRET_KEY=change-me-in-production`) and `docs/DEPLOYMENT.md:103` (`SECRET_KEY=<generate …>`).
- **Why it matters:** the code reads `DJANGO_SECRET_KEY`, but the example file and deploy guide tell you to set `SECRET_KEY`. `config("DJANGO_SECRET_KEY")` has **no default**, so python-decouple raises `UndefinedValueError` at import time → gunicorn fails to start. Following the shipped docs exactly = a dead-on-arrival production deploy. (The current committed `.env` contains neither key, so dev currently survives only via `dev.py`'s hardcoded fallback.)
- **Fix:** make the names consistent — either rename the read to `config("SECRET_KEY")` or change `.env.example` + `DEPLOYMENT.md` to `DJANGO_SECRET_KEY=` (and add it to the `.env` template). Add a startup sanity check.

### H2 — No login/link-confirm rate limiting (brute-force surface)
- **Files:** `accounts/views.py` (LoginView, no throttling), `accounts/google_views.py:129-181` (`GoogleLinkConfirmView.post` loops `check_password` with no attempt cap), `config/settings/base.py` (no `django-axes`/throttle middleware).
- **Why it matters:** the password login and — more subtly — the one-time Google link-confirm form both allow unlimited password attempts. The link-confirm path requires a valid Google session whose email matches an existing account, but once there it is an unpaced offline-guess surface. This is documented as deferred in **D27** ("login rate limiting is a pre-production blocker"), so it's a known, still-open gap — but it must not be forgotten at cutover.
- **Fix:** add `django-axes` (or a proxy/`fail2ban` rule) before production, and rate-limit `GoogleLinkConfirmView.post` specifically.

---

## 🟡 Medium

### M1 — `mark_fulfilling()` runs `select_for_update()` outside a transaction
- **File:** `orders/services.py:693-712` (`def mark_fulfilling` — no `@transaction.atomic`; body calls `InternalRequest.objects.select_for_update().get(...)`).
- **Why it matters:** every other `mark_*` (`mark_shipped`/`mark_received`/`mark_closed`) is `@transaction.atomic`. On PostgreSQL, `FOR UPDATE` executed in autocommit is a no-op — the row lock is silently never taken. It is only safe today because its sole caller (`inventory/services.py:issue_goods`) is itself atomic, so the lock inherits that transaction. This is a latent footgun: any future direct call would silently drop the lock and allow a status race.
- **Fix:** add `@transaction.atomic` to `mark_fulfilling` (harmless when nested inside `issue_goods`).

### M2 — No persistent DB connections (`conn_max_age=0`) under gunicorn
- **File:** `config/settings/base.py:72-80` (`dj_database_url.config(..., conn_max_age=0, conn_health_checks=True)`); the `POSTGRES_*` fallback also leaves `CONN_MAX_AGE` unset (0). `deploy/centcompras-gunicorn.service` runs 3 sync workers.
- **Why it matters:** every request opens and closes a new PostgreSQL connection (TCP + auth handshake). Functionally correct and the safe default, but it adds per-request latency and churn. With 3 workers and no connection reuse, the DB is hit with connect/disconnect for every API call.
- **Fix:** set `CONN_MAX_AGE` (e.g. 60) in `prod.py` (via `dj_database_url` or `DATABASES["default"]["CONN_MAX_AGE"]`) once you confirm worker count vs pool, or keep 0 if you add pgbouncer.

### M3 — N+1 in the warehouse request queue (`get_issue_summary`)
- **Files:** `orders/console_views.py:308-341` (`warehouse_request_list` → `_serialize_warehouse_request` → `inventory.services.get_issue_summary`), `inventory/services.py:get_issue_summary`.
- **Why it matters:** `warehouse_request_list` prefetches `lines__item`, but `get_issue_summary()` re-queries `request.lines` and, per line, calls `available_quantity(item)` (which does `Item.objects.get` + a `reserved_quantity` aggregate). Result: roughly `1 (lines) + 1 (issued aggregate) + 2 × num_items` queries **per request**, multiplied by N requests in the queue. Query count grows linearly with queue length and line count — a hot path for the warehouse.
- **Fix:** compute issued totals and reservations with grouped subqueries/annotations in a single pass (mirror `annotate_item_reservations`), and reuse the prefetched `lines__item` instead of re-fetching.

### M4 — Unbounded list/feed endpoints (no pagination)
- **Files:** `orders/console_views.py:124-131` (`request_list`), `threads/console_views.py:127-…` (`branch_thread_list`/`warehouse_thread_list`), `company_voice/console_views.py:feed_api` (`get_feed()`), `branches/console_views.py:39-45` (`branch_catalog_list`).
- **Why it matters:** these serialize the entire result set in one response. Products/manager-catalog and inventory are already paginated (`products/console_views.py:206,279`, `inventory/console_views.py:74,177`), but the branch catalog, request lists, thread lists, and the whole Company Voice feed return everything. Under production row counts this is large payloads + slow rendering (and the Company Voice feed reloads fully on every post/comment).
- **Fix:** paginate the request/thread lists; add a cap or lazy-loading to the Company Voice feed (already recorded as nit N1) and to the branch catalog.

### M5 — Google OAuth flow incompatible with the documented "Desktop app" dev client
- **Files:** `accounts/google_auth.py:get_google_client_config` (requires `client_secret`), `exchange_code_for_tokens` (sends `client_secret`, no PKCE), `docs/DEPLOYMENT.md` ("During dev: Desktop app type → loopback").
- **Why it matters:** Google **Desktop** clients are issued **no `client_secret`** and **mandate PKCE**. This code unconditionally requires a secret and never sends `code_verifier`/`code_challenge`, so the loopback "Desktop app" dev path described in the docs cannot work. The "Web application" client path (server-side secret) is correct and PKCE-less — so this is really a docs/config inconsistency that will bite whoever sets up OAuth from the guide.
- **Fix:** correct the deploy guide to always use a "Web application" client (even for loopback dev), or implement PKCE and make the secret optional.

### M6 — `create_post` not atomic (audit-integrity gap)
- **File:** `company_voice/services.py:185-199` (`create_post` creates the `VoicePost`, then writes `VoiceChangeLog` — no `@transaction.atomic`).
- **Why it matters:** if the changelog insert fails (e.g. transient DB error), the post persists without its audit row, breaking the audit-by-design invariant. Every other mutation service in the app is wrapped in `@transaction.atomic`.
- **Fix:** add `@transaction.atomic` to `create_post`.

---

## 🔵 Low

### L1 — Approval-limit rows read without lock during approve
- **Files:** `procurement/services.py:362` (`_approval_limit_for` → `.first()`), `orders/services.py:328` (`_assert_can_approve` → `.first()`); the writer (`update_approval_limit` / `update_branch_approval_limit`) *does* `select_for_update`.
- **Why it matters:** a concurrent admin edit of an approval cap could race an in-flight approval's limit check. Purely a business-config race with no data-integrity impact (and admin-only writes). Very low likelihood.
- **Fix:** optionally lock the `ApprovalLimit`/`BranchApprovalLimit` row in `_assert_can_approve`, or accept the benign race.

### L2 — `display_name` exposes the email local-part to all staff
- **Files:** `company_voice/services.py:display_name` (`email.split("@")[0]` fallback when `first_name` is empty); `company_voice/console_views.py` serializes it for every post/comment.
- **Why it matters:** non-anonymous posters without a `first_name` have their email prefix shown company-wide. Internal tool, so low impact, but it's an unnecessary disclosure.
- **Fix:** fall back to "User" (or require `first_name`) instead of the email local-part.

### L3 — OAuth `state` not cleared on early-return paths
- **File:** `accounts/google_views.py:60-84` (state-mismatch / missing-code returns happen **before** the `try` whose `finally` pops `oauth_state`).
- **Why it matters:** after a cancelled/mismatched callback the stale `oauth_state` remains in the session until the next login overwrites it. No security impact (state is only ever compared, and the value is regenerated each login), just sloppy session hygiene.
- **Fix:** clear `oauth_state` in the error branches too.

### L4 — HSTS preload + `SECURE_SSL_REDIRECT` vs shipped nginx (TLS ordering)
- **Files:** `config/settings/prod.py` (`SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS=31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`, `SECURE_HSTS_PRELOAD=True`), `deploy/centcompras-nginx.conf` (only `listen 80`, no 443).
- **Why it matters:** with the shipped nginx config there is no TLS listener, so `SECURE_SSL_REDIRECT` would 301 to a non-existent `https://` until certbot adds 443 (`DEPLOYMENT.md §10` covers this). HSTS `preload` + `include_subdomains` with a 1-year max-age is essentially irreversible for subdomains, so it must only be enabled after TLS is verified working.
- **Fix:** sequence the deploy as documented (certbot first), and consider lowering/removing `SECURE_HSTS_PRELOAD` until the domain is stable.

### L5 — No dedicated health-check endpoint
- **Files:** `config/urls.py`, `deploy/centcompras-gunicorn.service`.
- **Why it matters:** the only unauthenticated page is the login redirect; there is no `/healthz` for uptime monitors / LB health checks. gunicorn `--timeout 120` exists, but a monitor can't cheaply distinguish "app up" from "DB down".
- **Fix:** add a tiny unauthenticated health endpoint (returns 200 if DB reachable) and point the LB at it.

### L6 — gunicorn hardening gaps
- **File:** `deploy/centcompras-gunicorn.service` (`--workers 3 --timeout 120`, `Type=notify`, no `--max-requests`).
- **Why it matters:** no `--max-requests`/`--max-requests-jitter` means long-lived workers never recycle (slow memory growth); `Type=notify` relies on gunicorn's sd_notify support. Minor, but worth adding for a long-running prod box.
- **Fix:** add `--max-requests 1000 --max-requests-jitter 100` (and confirm systemd notify is actually exercised).

---

## ⚪ Nit

- **N1** — `config/settings/__init__.py` is empty. Harmless (the package resolves `config.settings.{dev,prod,test}` fine), but a stray `from config.settings import *` would break. Leave or add an explicit docstring.
- **N2** — `company_voice/services.py:display_name` has an unused `viewer` parameter.
- **N3** — Dead code already recorded in prior reviews: `threads/services.py:_bump`, `orders/models.py:InternalRequestQuerySet.for_user_branches`, `ThreadReadState.read_attr`. Not re-litigating; recorded only.
- **N4** — `ensure_default_branch_approval_limits()` / `ensure_default_approval_limits()` run `get_or_create` on every `post_migrate` (harmless, idempotent).

---

## ✅ Checked clean (explicitly)

- **CSRF:** no `csrf_exempt` anywhere in app code; every AJAX path sends `X-CSRFToken` (meta tag → `csrfToken()`); all POST forms include `{% csrf_token %}`. ✅
- **XSS:** zero `mark_safe`, zero `|safe`, zero raw `innerHTML` of unescaped user data in app templates/JS. `company_voice/feed.js` escapes `body` and `display_name` via `escapeHtml`, uses `textContent` for banners/i18n, and restricts tags to a server-validated allowlist (`KNOWN_TAGS` + `VALID_TAGS`). ✅
- **SQL injection:** no `.raw()`, `.extra()`, `RawSQL`, `connection.cursor()` or manual SQL in application code; all filters are parameterized (`icontains`, `Q`, `filter()`). ✅
- **Mass assignment:** every mutating service whitelists fields (`ITEM_UPDATABLE_FIELDS`, `PO_UPDATABLE_FIELDS`/`LINE_UPDATABLE_FIELDS`, `REQUEST_UPDATABLE_FIELDS`/`LINE_UPDATABLE_FIELDS`, etc.) and rejects unknown keys. ✅
- **IDOR / branch isolation:** branch-side request & thread lookups are scoped to `request.active_branch` (`_get_request_or_404`, `_get_thread_or_404`) → other-branch = 404, not 403. Warehouse endpoints are capability-gated (`warehouse_threads_required`, `internal_request_queue_required`, `deny_unless`). `adjust_stock` is admin-gated via `deny_unless(ADJUST_STOCK) → can_adjust_stock`. ✅
- **Admin exposure:** `accounts/admin_site.SuperuserAdminSite.has_permission` requires `is_superuser`; `django.contrib.admin` is replaced by `CentComprasAdminConfig`. Staff/warehouse users cannot reach `/admin/`. ✅
- **Lock ordering / reservations:** stock and `quantity_reserved` writes all serialize on the `Item` row (`select_for_update`), so `reserved_quantity()` reads inside `adjust_stock`/`issue_goods` are stable under the item lock — the D32 "never below reserved" invariant is not racy. Lock order (request/PO → item → line) is consistent across `receive_goods`, `issue_goods`, `approve`, `cancel`, `release_reservations_for_request`; no deadlock identified. Multi-item operations sort item pks (`order_by("pk")`). ✅
- **PO approval snapshot:** `submit`/`approve` lock the PO; line edits lock the PO before the line; `approved_net/vat/gross` frozen at approve. ✅
- **Company Voice races:** `edit_post`/`delete_post`/`add_comment`/`edit_comment`/`delete_comment` all `select_for_update` the post/comment; `_get_or_create_sub_thread` uses a savepoint + `IntegrityError` retry; PATCH requires `updated_at` with `_require_fresh` → 409 `stale_edit`. ✅
- **Sessions/hijacking:** `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` set in prod; Django `login()` rotates the session key (no fixation); `UserTimezoneMiddleware` activates/deactivates per request with `finally`. ✅
- **Secrets/config hygiene:** `.env` is gitignored (`.gitignore` re-includes only `.env.example`); no hardcoded secrets in tracked Python (only the dev `DJANGO_SECRET_KEY` fallback, which is explicitly dev-only). `DEBUG=False` in prod. ✅
- **Dependencies:** `requirements.txt` uses bounded ranges (`Django>=6.1,<7`, `psycopg[binary]>=3.1,<4`, `gunicorn>=21.2`, `whitenoise>=6.6`, etc.) — upper bounds present, no known-risky pins. ✅
- **Migrations for a fresh DB:** run cleanly in order (unique + `CheckConstraint`s at the DB layer; `products/0002` seeds VAT rates; `orders/0002` backfills `quantity_reserved`). No `RunPython` that assumes existing data will break on an empty production DB. ✅
- **Signals / logging / connections:** `post_migrate` receivers are guarded to their own app and only `get_or_create` idempotent rows; `logging_utils` uses `ConcurrentRotatingFileHandler`, no DB access in `ready()`, no manual cursors/connection leak, no threading touching the DB. ✅
- **Open redirect:** `LoginView.get_success_url` delegates to Django's `RedirectURLMixin.get_redirect_url`, which validates `next` against allowed hosts. ✅

---

## Bottom line

Fix **H1** (secret wiring) and **H2** (rate limiting) before cutover, then address **M1–M6** opportunistically. The concurrency and authorization design is a genuine strength of this codebase — the remaining items are mostly deployment hygiene and unbounded-read scaling, not correctness defects.
