# Code Review — full tree, production readiness (`main` @ `c7c3432`)

> **Status (26 August 2026, 12:45 WEST):** **P0, P1, and P2 applied** in the working tree. Leftover nits from *earlier* reviews remain recorded, not a queue. Original read-only findings follow; see **Resolution** for what shipped.

**Date:** 2026-08-26  
**Repo:** `/home/pmpmt/python/260826-central_de_compras/warehouse_V2`  
**Branch reviewed:** `main` @ `c7c3432` (in sync with `origin/main`)  
**Working tree:** local `.env.example` only — ignored for this review  
**Suite at review time:** last recorded **540 OK** (26 Aug, after Phase 6 review fixes). **Suite after fixes:** **548 OK**.

**Scope:** entire live tree as if preparing for first production VPS day — authz, concurrency, stock/FIFO, tenancy, offline/PWA, production settings, deploy artifacts. Not a PR diff. **Not** Phase 7 deploy execution and **not** Phase 8 OAuth/chrome product work, except where current code/docs would fail a first boot or first multi-user day.

---

## How this review was done

| Reviewer | Scope | Method |
|----------|--------|--------|
| Parent (this document) | Full tree | Independent read/grep of settings, auth, services, SW/IDB, deploy; verified every sub-agent finding against current code |
| Independent reviewer ([review](8fd30e16-97b1-43a7-b24a-9e7a9edc0d78)) | Full tree | Parallel read-only pass (Grok 4.6; requested Opus hit Other-Models quota) |
| Bugbot ([review](83003b62-29ac-4f56-8fda-0acee6fad4b2)) | Full tree (natural-language scope; no feature-branch diff) | Parallel bug-finding pass |

Disagreements were resolved by parent verification (see [Comparison](#comparison)). Unified IDs below are the ones to act on.

**Already applied — do not re-open** unless an ID below says it is still broken: 2208 P0–P4; 1303 N1–N12; threads M1–M5 / L1–L6; Company Voice H1 / M1–M9 / L1–L8; chrome H1–H3 / M1 / L1 / L2; 24 Aug production-readiness H1 / H2 / M1–M3 / M5–M7; Phase 6 offline P0 / P1 / P2.

---

## Resolution (26 Aug 2026, later session)

| Batch | Status | Summary |
|-------|--------|---------|
| **P0** (H1, H2) | Applied | Network-first `/branch/` HTML; per-user pending rows; IndexedDB wipe on Sign out |
| **P1** (M1–M8) | Applied | Sync IntegrityError upsert; JSON 400; Google `is_active`; prod `DATABASE_URL`; SSL env-gate; throttle prune; `USE_X_FORWARDED_HOST=False`; list cap 200 |
| **P2** (L1–L6, N1) | Applied | gunicorn `--max-requests`; `/healthz`; session iterator; safe `next`; prod INFO logs; prod Google redirect check; SECRET_KEY fail-fast via decouple |

---

## Summary

The warehouse core is still a strength: `services.py` mutations, `select_for_update` + consistent item pk lock order, FIFO reservation, PO approved-totals snapshot, branch 404 isolation, CSRF on POSTs, and no `mark_safe` / `|safe` / raw SQL. Prior High/Medium items from August reviews are present in the code as claimed.

It is **not ready for a first multi-user production day**. Two High issues in the Phase 6 offline client will mis-attribute or cross-branch-sync drafts on shared branch tablets (the realistic PWA deployment). Several Medium first-boot and robustness holes remain (prod `DATABASE_URL` fallback, HTTPS-redirect vs HTTP-only nginx sample, Host-header trust, JSON 500s, Google login of deactivated users, login-throttle write amplification).

No Critical security defect (no authz bypass that grants warehouse rights to a branch user; stock cannot go negative via the ledger path; XSS probe surface is still `textContent` / escaped `innerHTML`).

---

## Verdict: **ISSUES FOUND — not production-ready**

Do not treat as deploy-ready until **P0 (H1, H2)** is applied. Apply **P1 (M4, M5, M7)** before the first VPS boot. **P1 remainder + P2** in the same follow-up or immediately after.

| Count | Severity |
|-------|----------|
| 0 | Critical |
| 2 | High |
| 8 | Medium |
| 6 | Low |
| 1 | Nit |

---

## Findings (unified — act on these IDs)

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| H1 | High | `branches/templates/branches/service_worker.js:69-87` | Cache-first HTML for all `/branch/` GETs; stale `data-branch-id` / identity defeats Phase 6 P0 branch guard |
| H2 | High | `branches/static/branches/js/db.js`; `branch_bootstrap.js:7-10`; logout form | IndexedDB queue is origin-scoped, not per-user; not cleared on logout; next user auto-syncs prior drafts as themselves |
| M1 | Medium | `orders/services.py:385-413` | Concurrent `client_uuid` sync → uncaught `IntegrityError` **500** (unique constraint saves data) |
| M2 | Medium | `orders/console_views.py:106-156` (and other branch POSTs); `threads/console_views.py:154` | `_parse_body` / `_parse_json` **outside** `try`; non-object JSON → **500**. Threads 24 Aug M1 is **incomplete** |
| M3 | Medium | `accounts/google_views.py:107-147`, `163-206` | Google login / link-confirm do not check `is_active`; password login does |
| M4 | Medium | `config/settings/base.py:82-100`; `prod.py:3-4` | Prod does **not** fail-fast on missing `DATABASE_URL`; falls back to `appuser` / `your_password_here` |
| M5 | Medium | `config/settings/prod.py:21-26`; `deploy/centcompras-nginx.conf` | `SECURE_SSL_REDIRECT` + HSTS preload + HTTP-only nginx sample → site unreachable until certbot |
| M6 | Medium | `accounts/throttle.py`; nginx sample | Username-only lock; `LoginFailure` rows never pruned; `REMOTE_ADDR` is `127.0.0.1` behind nginx |
| M7 | Medium | `config/settings/prod.py:31`; `deploy/centcompras-nginx.conf:19-22` | `USE_X_FORWARDED_HOST = True` but nginx does not set/strip `X-Forwarded-Host` (Host-header poisoning) |
| M8 | Medium | `orders/services.py:851-860`; `threads` lists; `company_voice/services.py:346-351`; branch catalog API | Unbounded list/feed payloads (24 Aug M4, still open). Voice feed was recorded as CV N1 |
| L1 | Low | `deploy/centcompras-gunicorn.service:13-18` | No `--max-requests`; workers never recycle (recorded 24 Aug, still present) |
| L2 | Low | `config/urls.py` | No `/healthz`; systemd `Type=notify` is “gunicorn up”, not “DB up” |
| L3 | Low | `accounts/views.py:81-90` | “Sign out other devices” decodes **every** `Session` row |
| L4 | Low | `accounts/views.py:92` | `logout_other_devices` redirects to raw `POST next` (UI does not send `next`; SameSite limits exploit) |
| L5 | Low | `logging_utils/logging_config.py:21-25` | Default console/file level **DEBUG** in production |
| L6 | Low | `config/settings/base.py:141-144` | `GOOGLE_OAUTH_REDIRECT_URI` defaults to `http://localhost:8000/...` in prod inherit |
| N1 | Nit | `config/settings/prod.py:15-16` | Comment claims empty `SECRET_KEY` “fails fast”; it does, but via Django 6.1 `ImproperlyConfigured`, not decouple |

---

### H1 — Service Worker cache-first for authenticated `/branch/` HTML

**Evidence.** Bypass is only `/api/`, `/accounts/`, `/admin/`, `/manage/`. Every other GET under `/branch/` (dashboard, catalog, requests, threads, receipts, **select**) is cache-first:

```69:87:branches/templates/branches/service_worker.js
    if (url.pathname.indexOf(BRANCH_PATH_PREFIX) === 0 || APP_SHELL.indexOf(url.pathname) !== -1) {
        event.respondWith(
            caches.match(event.request).then(function (cached) {
                var networkFetch = fetch(event.request)
                    .then(function (response) {
                        if (response && response.ok) {
                            var copy = response.clone();
                            caches.open(CACHE_NAME).then(function (cache) {
                                cache.put(event.request, copy);
                            });
                        }
                        return response;
                    })
                    .catch(function () {
                        return cached;
                    });
                return cached || networkFetch;
            })
        );
```

`return cached || networkFetch` serves yesterday’s HTML while the network update is in-flight. Those pages embed `data-branch-id`, role, CSRF meta, email, and `data-can-approve`. Phase 6 P0 (`sync_queue.js:11-20`) compares the queue’s `branch_id` to **DOM** `data-branch-id`, while the server uses **session** `request.active_branch`.

**Why it matters.** Dual-branch user (`branch.dual@…`) or shared tablet: client HTML still says North, session is South → `isWrongBranch` does not fire → `POST /api/branch/requests/sync/` creates the draft on South. Also shows the previous user’s name/role until a later navigation. Online is enough; this is not an offline-only bug.

**Fix (executable):**

1. Treat navigations / HTML as **network-first**: `fetch` then `cached` only on failure. Do **not** `cache.put` document responses (or cache a generic offline shell without user/branch attributes).
2. Keep cache-first only for `/static/` and `APP_SHELL` (versioned CSS/JS, manifest, icon).
3. Bump `CACHE_NAME` (`centcompras-branch-v5` → `v6`) and bump `?v=` on every template that references `register_sw.js` / the SW (house rule).
4. Optional hardening: a tiny uncached `GET /api/branch/session/` (no-store) returning `{branch_id, user_id}` that `sync_queue.js` uses instead of DOM attributes.

**Tests / smoke:** log in dual-branch user; cache `/branch/catalog/` on North; switch to South; hard-navigate `/branch/requests/` — HTML `data-branch-id` must be South on first paint, not North. DevTools → Application → Cache Storage must not keep per-user HTML.

---

### H2 — IndexedDB pending queue is not per-user and survives logout

**Evidence.** DB name is a single origin store (`centcompras_branch`). Pending rows are keyed by `client_uuid` only (`db.js:22-24`). They store `branch_id` but **not** user id. Every branch page auto-drains (`branch_bootstrap.js:7-10` → `bindAutoSync` → `drainQueue` immediately). Logout is a normal POST with no IDB wipe:

```20:22:products/templates/products/includes/account_settings.html
                <form method="post" action="{% url 'logout' %}" class="settings-signout-form">
                    {% csrf_token %}
                    <button type="submit" class="settings-signout-link" data-i18n="signOut">Sign out</button>
```

No `data-user-id` on branch `<body>` tags (only `data-branch-id`, plus `data-can-approve` on requisição).

**Why it matters.** Shared counter tablet: Operator A queues an offline requisição, logs out. Operator B logs in at the same branch → auto-sync POSTs A’s lines as **B** (`created_by=B`). Same-branch H1 guard does not apply. First multi-user day, not an edge case.

**Fix (executable):**

1. Add `data-user-id="{{ user.id }}"` on every branch `<body>` that already has `data-branch-id` (catalog, dashboard, threads, receipts, requests).
2. Persist `user_id` on `pending_requests` at queue time (`orders/static/orders/js/branch_requests.js` write path).
3. In `sync_queue.js` `isEligibleForDrain` / `isWrongBranch`: skip entries whose `user_id` ≠ current `data-user-id` (treat missing `user_id` as skip, not drain — safer for leftover rows).
4. On Sign out (settings form submit): `indexedDB.deleteDatabase('centcompras_branch')` (or clear `pending_requests` + catalog) **before** the POST proceeds (`beforeunload` is too late; use `event.preventDefault` + `form.submit()` after IDB delete, or a small shared `offline_logout.js`).
5. Bump `db.js` / `sync_queue.js` / `branch_requests.js` / `branch_bootstrap.js` `?v=` everywhere referenced.

**Tests / smoke:** user A offline-queues a draft; sign out; user B signs in same browser/branch; confirm queue does **not** POST A’s UUID as B. Sign-out must leave IndexedDB empty (Application → IndexedDB).

---

### M1 — Concurrent `client_uuid` sync is not upserted

**Evidence.** Lookup then insert, unique on `InternalRequest.client_uuid`, no `IntegrityError` handler:

```391:413:orders/services.py
    existing = (
        InternalRequest.objects.filter(client_uuid=parsed_uuid)
        ...
        .first()
    )
    if existing is not None:
        ...
        return existing, False

    request = InternalRequest(...)
    request.save()
```

`request_sync` only catches `ValidationError`. Unique constraint protects data; the loser 500s. Double-submit / two tabs (Phase 6 leftover L2) hits this. `add_line` already has the IntegrityError pattern at `orders/services.py:472`.

**Fix:** `try/except IntegrityError` around `save()`: re-fetch by `client_uuid`, if `branch_id` mismatches raise `client_uuid_branch_mismatch`, else return `(existing, False)`. Optionally `select_for_update()` on the winning row before adding lines.

**Test:** `TransactionTestCase` two threads `sync_internal_request` same UUID → one 201/created, one 200/existing, **no** 500.

---

### M2 — Uncaught JSON `ValidationError` / non-object body → 500

**Evidence.** Orders helper does not require a dict and raises `ValidationError` that many views never catch:

```106:110:orders/console_views.py
def _parse_body(request):
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValidationError("Request body must be valid JSON.", code="invalid_json")
```

`request_create` / `request_sync` / add-line / update parse **outside** `try` (`console_views.py:144-156`, `188-200`, …). Invalid JSON → uncaught `ValidationError` → Django **500**. JSON array then `data.get(...)` → `AttributeError` 500.

Warehouse issue/short-close wrap parse inside `try` (`395-407`). Products / inventory / procurement / Company Voice wrap parse inside `try` and reject non-dicts.

Threads `_parse_json` **does** reject non-dicts (`threads/console_views.py:43-50`) but `branch_thread_create` still calls it **outside** `try` (`:154`) — invalid JSON is still 500. 24 Aug threads M1 is **incomplete**.

**Fix:**

1. Make `orders.console_views._parse_body` match products: dict check + `code="invalid_json"`.
2. Move every `_parse_body` / `_parse_json` call **inside** the existing `except ValidationError` (or return 400 from the helper).
3. Same for remaining threads POSTs (`branch_thread_create`, reply, close, warehouse equivalents).

**Tests:** `POST /api/branch/requests/sync/` with body `[]`, `{`, and `"not-object"` → **400** `invalid_json`, never 500. Same for `POST /api/branch/threads/`.

---

### M3 — Google OAuth logs in deactivated users

**Evidence.** Lookup is `User.objects.filter(email=google_email).first()` with no `is_active` check; `_login_google_user` writes name/flags then `login()` (`google_views.py:107-147`). Link-confirm (`163-206`) same. Password `LoginView` uses `authenticate()`, which refuses inactive users.

**Why it matters.** Offboarding + later `AUTH_MODE=google_only` (intended prod). User sees “Welcome back!” and gets a session cookie. Next request: `ModelBackend.get_user` returns `None` for inactive; most app gates then 401/login. `branch_select` is `@login_required` only (no `deny_if_inactive`) so they bounce as anonymous. Not a privilege escalation, but the kill-switch is inconsistent and `_login_google_user` **mutates** a deactivated row (`is_google_account=True`).

**Fix:** If `not user.is_active`: message + redirect to login, **do not** `save()` or `login()`. Same on link-confirm. Add a test.

---

### M4 — Prod does not fail-fast on missing `DATABASE_URL`

**Evidence.** `prod.py:3-4` claims `DATABASE_URL` is required. `base.py:82-100` uses it only if set; else `POSTGRES_USER` default `appuser`, password `your_password_here`. Gunicorn starts; first request `OperationalError` (or connects to a leftover local role).

`ALLOWED_HOSTS` has no default (decouple fail-fast). Empty `SECRET_KEY` fails via Django 6.1 (`ImproperlyConfigured`) when WSGI loads — **not** a High (see Comparison). `DATABASE_URL` is the remaining boot gap.

**Fix:** In `prod.py`, after import:

```python
from django.core.exceptions import ImproperlyConfigured

if not config("DATABASE_URL", default=""):
    raise ImproperlyConfigured("DATABASE_URL is required in production.")
```

Do not inherit the `appuser` / `your_password_here` fallback when `DJANGO_SETTINGS_MODULE` is `config.settings.prod`.

---

### M5 — First VPS boot: HTTPS redirect with HTTP-only nginx

**Evidence.** `prod.py` sets `SECURE_SSL_REDIRECT = True`, `SECURE_HSTS_SECONDS = 31536000`, `INCLUDE_SUBDOMAINS`, **and** `SECURE_HSTS_PRELOAD = True`. Sample nginx listens on **80 only** and sets `X-Forwarded-Proto $scheme`. `DEPLOYMENT.md` order: gunicorn (8) → nginx (9) → certbot (10).

**Why it matters.** Between 8 and 10, browsers hit HTTP, Django 301s to HTTPS, nothing listens on 443. Operators think nginx is broken. HSTS preload must not be advertised until the domain is submitted to the preload list and 443 is real.

**Fix (pick one, document it in `DEPLOYMENT.md` — do not skip the doc change):**

- Do not start gunicorn on `prod` until certbot has 443, **or**
- Gate `SECURE_SSL_REDIRECT` on env `SECURE_SSL_REDIRECT` default `False` until TLS exists, **or**
- Ship an HTTP nginx server that only proxies `/.well-known/acme-challenge/` plus a “waiting for TLS” page.

Set `SECURE_HSTS_PRELOAD = False` until the domain is actually submitted. Keep HSTS seconds only **after** 443 works.

---

### M6 — Login throttle gaps (public internet)

**Evidence.** Lock is `username__iexact` count in a window (`throttle.py:23-34`). `record_failure` always `create()`s; nothing deletes rows except successful login for **that** username (`44-48`). Client IP is `REMOTE_ADDR` (`views.py:12-13`) → always `127.0.0.1` behind the sample nginx (`proxy_set_header X-Real-IP` is unused by Django). No per-IP cap.

**Why it matters.** Attacker posts random usernames: unbounded `accounts_loginfailure` inserts, no lockout. Known seed emails get 5 guesses / 15 min — acceptable. Table growth + DB write amplification is the prod issue. Forensic IP is useless.

**Fix:**

1. Prune rows older than the window inside `record_failure` (or a management command + cron).
2. In nginx: `limit_req` on `/accounts/login/` and `/accounts/google/` (preferred — do not blindly trust client `X-Forwarded-For`).
3. If recording IP: use nginx `X-Real-IP` via `SECURE_PROXY_SSL_HEADER`-style config **only** after nginx overwrites that header (same class of bug as M7).

Do **not** replace the DB throttle with a per-process cache (24 Aug H2 reason: gunicorn workers).

---

### M7 — `USE_X_FORWARDED_HOST` without nginx overwrite

**Evidence.** `prod.py:31` `USE_X_FORWARDED_HOST = True`. Sample nginx sets `Host $host` but does **not** set or unset `X-Forwarded-Host`. Django then prefers attacker-supplied `X-Forwarded-Host` for `request.get_host()` / `build_absolute_uri()` (OAuth redirect construction in `google_auth.get_redirect_uri` when settings URI is empty; absolute URLs; CSRF origin pairing).

**Fix (do both):**

1. nginx: `proxy_set_header X-Forwarded-Host $host;` (and keep `Host $host`).
2. Simpler/safer: set `USE_X_FORWARDED_HOST = False` in prod — nginx already passes the real `Host`. Keep `SECURE_PROXY_SSL_HEADER` + `USE_X_FORWARDED_HOST` only if you also overwrite the header.

---

### M8 — Unbounded list/feed payloads

**Evidence.** `get_internal_requests` returns the full queryset (`orders/services.py:851-860`). Thread list payloads have no pagination (threads leftover N4). `get_feed()` is unbounded (`company_voice/services.py:346-351` — recorded as CV N1). Branch catalog API is a full snapshot (acceptable for offline cache, but grows with catalogue size). Products/inventory consoles already paginate.

**Why it matters.** Warehouse `/manage/internal-requests/` and `/manage/threads/` are all-branches queues. First year of real volume will make every console load expensive. Not a correctness bug.

**Fix:** Cap or paginate warehouse request list and warehouse/branch thread lists (page size aligned with item console). Leave Company Voice feed as documented FAQ **or** add a hard cap (e.g. 200) if the executing session is already touching `get_feed`. Branch catalog snapshot may stay full (offline requirement) — optional `ETag` / incremental later, not this batch.

---

### L1 — gunicorn never recycles workers

`deploy/centcompras-gunicorn.service`: `--workers 3 --timeout 120`, no `--max-requests`. **Fix:** `--max-requests 2000 --max-requests-jitter 200`.

### L2 — No health endpoint

No `/healthz`. **Fix:** unauthenticated `GET /healthz` that `SELECT 1` and returns 200/503. Allow in nginx without auth. Optional systemd `ExecStartPost` or LB check.

### L3 — Logout-other-devices scans all sessions

`Session.objects.all()` + `get_decoded()`. Fine at tens of users; painful at thousands of leftover rows. **Fix:** iterate `.iterator()` for now; later a `UserSession` table mapping `session_key` → user on login.

### L4 — Unvalidated `next` on logout-other-devices

```92:92:accounts/views.py
    return redirect(request.POST.get("next") or settings.LOGIN_REDIRECT_URL)
```

The settings form does **not** send `next`. Django’s `LogoutView` validates `next` via `RedirectURLMixin`; this custom view does not. Cross-site POST is blocked by SameSite=Lax CSRF/session cookies, so severity is Low.

**Fix:** `url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()})` (and require relative paths). Default to `request.META.get("HTTP_REFERER")` only after the same check, or drop `next` entirely.

### L5 — DEBUG logging in production

`logging_utils` defaults `console_level` / `file_level` to **DEBUG**. Under gunicorn this writes noisy rotating files (PII in emails already logged on Google miss). **Fix:** if `not settings.DEBUG`, default to INFO (keep DEBUG in `dev.py`).

### L6 — Google redirect URI default is localhost

`base.py` sets `GOOGLE_OAUTH_REDIRECT_URI` default `http://localhost:8000/accounts/google/callback/`. Prod inherits it. Password login still works (`AUTH_MODE=both`). Breaks Google login at first deploy if credentials are set and this env is forgotten. **Fix:** in `prod.py`, if `GOOGLE_CLIENT_ID` is set and redirect URI still contains `localhost`, `ImproperlyConfigured`. Phase 8 can still own the Web-client rollout.

### N1 — SECRET_KEY comment vs mechanism

`prod.py:16` `default=""`. Django 6.1 raises `ImproperlyConfigured("The SECRET_KEY setting must not be empty.")` when the setting is accessed at WSGI load — gunicorn workers **will not** serve with an empty key. Bugbot’s “empty key boots” finding is **rejected**. Optionally use `config("DJANGO_SECRET_KEY")` with **no** default so decouple fails with a clearer env-var name.

---

## Comparison

| Topic | Bugbot | Independent | Parent | Unified |
|-------|--------|-------------|--------|---------|
| Empty `SECRET_KEY` gunicorn boot | **High** | Rejected (Django fail-fast) | Confirmed Django 6.1 empty-key check; WSGI load fails | **Not a finding** (N1 comment only) |
| Sync UUID `IntegrityError` 500 | Medium | **M1** | Confirmed unique + no handler | **M1** |
| `logout_other_devices` `next` | Medium | Not raised | Confirmed; UI omits `next`; SameSite | **L4 Low** |
| SW cache-first `/branch/` HTML | — | **H1 High** | Confirmed `cached \|\| networkFetch` | **H1** |
| IDB queue survives logout / shared user | — | **H2 High** | Confirmed no `user_id`, auto-sync, no wipe | **H2** |
| JSON parse outside `try` | — | **M2** | Confirmed orders + threads create | **M2** |
| Google `is_active` | — | **M3** | Confirmed; also mutates deactivated row | **M3** |
| `DATABASE_URL` fallback | — | **M4** | Confirmed | **M4** |
| SSL redirect vs HTTP nginx | — | **M5** | Confirmed + HSTS preload | **M5** |
| Throttle IP / prune | — | **M6** | Confirmed | **M6** |
| `USE_X_FORWARDED_HOST` | — | — | Confirmed nginx does not overwrite | **M7** |
| Unbounded lists | — | Noted leftover | Still open (24 Aug M4) | **M8** |
| gunicorn `--max-requests` / `/healthz` / session scan | — | L1–L3 | Confirmed | **L1–L3** |
| DEBUG logs / OAuth localhost URI | — | — | Confirmed | **L5, L6** |

---

## Checked-clean (do not re-investigate unless a fix regresses)

- **Stock / FIFO / PO snapshot / branch receipt:** `transaction.atomic` + `select_for_update`; items locked in pk order; `issue_goods` refuses `qty > reserved`; `item_quantity_gte_zero` / `quantity_reserved` constraints; `unique_branch_item_stock`.
- **`mark_fulfilling`:** still `@transaction.atomic` (24 Aug M1).
- **`conn_max_age=60`** + health checks when `DATABASE_URL` is set (24 Aug M2).
- **OAuth PKCE S256**, existing-only, `email_verified` required, `oauth_state` cleared in `finally` (24 Aug M5). Gaps: **M3**, **L6**.
- **Login throttle present** and DB-backed (24 Aug H2). Gaps: **M6**.
- **CSRF:** no `csrf_exempt`; AJAX sends `X-CSRFToken`. Logout is POST.
- **XSS:** no `mark_safe` / `|safe`. Consoles use `textContent`. `feed.js` `innerHTML` goes through `escapeHtml` + allow-listed tags.
- **SQL injection:** no `raw` / `extra` / `cursor`.
- **Mass assignment:** item updaters exclude `quantity`; PO/request updaters whitelist fields.
- **Branch isolation:** `_get_request_or_404(..., branch=)` 404; other-branch threads 404; catalog serializer omits cost.
- **Admin:** `SuperuserAdminSite.has_permission` requires `is_superuser` and `is_active`.
- **DEBUG:** hardcoded `False` in `prod.py`; `.env` `DEBUG=` cannot turn it on.
- **SECRET_KEY names:** `DJANGO_SECRET_KEY` with legacy `SECRET_KEY` fallback — still aligned.
- **Phase 6 P0 H2–H4 / M2** still in code (stale `syncing` reset, extra lines, global UUID, `unknown_item`). **P0 H1 client guard is still in `sync_queue.js` but H1 (this review) defeats it.**
- **Company Voice / chrome applied items:** not re-opened.

---

## Previously applied items — still broken?

| Item | Status |
|------|--------|
| 24 Aug **H1** SECRET_KEY env name | **Still fixed.** Empty key fail-fast is Django, not decouple (N1). |
| 24 Aug **H2** login throttle | **Present.** Username lock works; IP/DoS gap is **M6**. |
| 24 Aug **M1–M3, M5–M7** | **Still applied.** |
| Threads **M1** JSON 400 | **Incomplete** → this review **M2**. |
| Phase 6 **P0 H1** wrong-branch sync | Logic still in JS; **this H1** serves stale `data-branch-id` so the guard misses. |
| Phase 6 leftover L1/L2/L5/L7/N3 | Still nits — **not this queue.** L2 (multi-tab RMW) is related to **M1** but not a substitute. |
| 24 Aug unbounded lists **M4** | **Still open** → **M8**. |
| Chrome leftover L3–L8 / N1–N3 | Recorded for Phase 8 — **not this queue.** |
| Threads N1–N6, Company Voice N1 | Recorded — **not this queue** except volume overlap in **M8**. |

---

## Suggested act-on order (executing agent)

Do **not** start Phase 7 VPS work, Phase 8 chrome/OAuth product, or Phase 9 email in this follow-up. Do **not** edit `.cursor/plans/*` or retitle Phase 7 unless the user asks. Do update user manuals **only** if behaviour/error strings change (H2 logout wipe, H1 cache semantics, new 400 codes).

### P0 — must before first multi-user / PWA day

1. **H1** — network-first HTML; bump SW cache name + `?v=`.
2. **H2** — per-user pending rows + IDB wipe on logout; bump JS `?v=`.
3. Tests + manual smoke in H1/H2 sections.
4. Full suite: `.venv/bin/python manage.py test products accounts procurement inventory branches orders threads company_voice --noinput`

### P1 — must before first VPS boot + remaining Medium

5. **M4** — prod `DATABASE_URL` fail-fast.
6. **M5** — TLS order / env-gate SSL redirect; `SECURE_HSTS_PRELOAD = False`; `DEPLOYMENT.md`.
7. **M7** — overwrite or disable `USE_X_FORWARDED_HOST`.
8. **M1** — `IntegrityError` upsert on sync.
9. **M2** — JSON 400 on orders + remaining threads POSTs.
10. **M3** — refuse inactive Google users.
11. **M6** — prune throttle rows; nginx `limit_req` note in `DEPLOYMENT.md`.
12. **M8** — paginate or cap warehouse request + thread lists (voice feed optional cap).

### P2 — with the same PR if cheap, else immediately after

13. **L1–L6** as listed.
14. **N1** optional (drop empty-string default).

After the fix pass: session-handoff skill (handoff, PROJECT-PLAN tracker tick for this review, README if URLs/settings changed). **Do not** mark Phase 7 complete — this review is a pre-deploy hardening slice, not VPS provisioning.

---

## Test gap notes (would have caught these IDs)

1. Dual-branch / shared-browser: SW cached HTML vs session branch (**H1**).
2. Logout then second user: pending queue must not sync (**H2**).
3. Concurrent `sync_internal_request` same UUID (**M1**).
4. Orders/threads POST `[]` / `{` → 400 (**M2**).
5. Google callback for `is_active=False` does not `login()` (**M3**).
6. Importing `config.settings.prod` without `DATABASE_URL` raises (**M4**) — use env isolation in the test process.

---

## Out of scope / not findings

- Phase 7 droplet/DNS/certbot **execution** (this report only hardens code/docs so that execution can succeed).
- Phase 8 shared chrome and Google **production rollout** as a product phase (L6 is only the localhost default footgun).
- Phase 9 real email (`notify_supplier_on_approval` stub).
- Leftover recorded nits (threads N1–N6, CV N1 except M8 overlap, chrome L3–L8 / N1–N3, Phase 6 L1/L5/L7/N3).
- WhiteNoise hashed `STORAGES` — nginx `/static/` alias is the prod path; `?v=` remains the cache-buster.
- Public signup / password reset (not built).

---

## Manual smoke (after P0)

Use **`http://127.0.0.1:8000`** only (not mixed with `localhost`).

1. Seed / log in `branch.manager.north@centcompras.dev` / `devpass123`.
2. Cache `/branch/catalog/` online; DevTools offline → requisição draft queued.
3. Sign out (IDB pending store must be gone) → log in `branch.operator.north@…` → no auto-upload of the previous draft.
4. Dual-branch `branch.dual@…`: North draft, switch South online, open `/branch/requests/` — first paint `data-branch-id` is South; North draft does not POST until switched back.
5. `POST /api/branch/requests/sync/` as an authenticated branch user with body `[]` → 400 JSON, not Django debug/500 HTML.

---

*Report produced 26 August 2026, 12:05 WEST. Read-only review; this file is the work queue for the executing agent.*
