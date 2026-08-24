# Production Readiness Review — Combined Report (24 Aug 2026)

> Two independent reviews compared: parent (main agent) + dedicated subagent.
> Scope: multi-user concurrency & race conditions, database connection lifecycle,
> and overall security for near-production readiness. Fresh prod DB (greenfield)
> — data concerns out of scope; code correctness under real multi-user load is in.

---

## Verdict: 🔶 NEARLY READY → ✅ FIXES LANDED (24 Aug, later session)

The concurrency and authorization model is a **real strength** — disciplined
`select_for_update` + `transaction.atomic` with consistent lock ordering, and
real unique constraints backing every `get_or_create`. No Critical findings.

**Post-review fixes applied in the same day (all tested, 528 suite green):**

| # | Status | Fix |
|---|--------|-----|
| **H1** | ✅ Fixed | `prod.py` now reads `DJANGO_SECRET_KEY` with fallback to legacy `SECRET_KEY`; `.env.example` + `docs/DEPLOYMENT.md` aligned to `DJANGO_SECRET_KEY` |
| **H2** | ✅ Fixed | DB-backed login throttle (`accounts/throttle.py` + `LoginFailure` model + migration 0005): 5 failures / 15 min locks the username; wired into password login **and** Google link-confirm; success clears; shared across gunicorn workers (DB, not per-process cache) |
| **M1** | ✅ Fixed | `mark_fulfilling` now `@transaction.atomic` |
| **M2** | ✅ Fixed | `conn_max_age=60` (persistent connections + health checks) |
| **M3** | ✅ Fixed | Warehouse request list N+1 → batch `get_issue_summaries()` (2 queries, not 2+ per request) |
| **M5** | ✅ Fixed | PKCE (S256) added to Google OAuth: verifier stored in session, `code_challenge` in auth URL, `code_verifier` at token exchange |
| **M6** | ✅ Fixed | `create_post` now `@transaction.atomic` (post + audit log commit together) |
| **M7** | ✅ Fixed | **"Sign out other devices"** button in the account settings popover (POST-only, `login_required`): deletes every session for the user except the current one. Independent per-device sessions remain the default; this is the user-triggered revocation path |

**Deliberate call (H2):** custom DB-backed throttle instead of django-axes — no new
dependency on a very new Django 6.1, fully testable, shared across workers.
Upgrade path to django-axes remains if per-IP lockout UI is wanted later.

---

## Ship-blocking findings (as of report time)

---

## 🔴 Critical — none

Both reviewers independently found **zero** critical issues. Core stock-ledger,
FIFO-reservation (D32), PO-approval-snapshot, and branch-receipt paths are
correctly atomic, row-locked in consistent pk order (no deadlock vector found).

---

## 🟠 High — MUST FIX before prod

| # | Finding | Where | Fix |
|---|---------|-------|-----|
| **H1** | **SECRET_KEY env-var name mismatch breaks prod boot.** `prod.py` reads `config("DJANGO_SECRET_KEY")` (no default), but `.env.example` documents `SECRET_KEY=change-me-in-production`. Follow the docs → `UndefinedValueError` at import → gunicorn refuses to start. | `config/settings/prod.py:13`, `.env.example:6`, `docs/DEPLOYMENT.md` | Align names: read `config("DJANGO_SECRET_KEY", default=config("SECRET_KEY", default=None))` or rename everywhere. One-line fix; **do this before first deploy**. |
| **H2** | **No login rate limiting.** Password login (`auth_views.LoginView`) and the Google link-confirm password check both run unthrottled — `check_password` can be looped. Seed emails are documented, so online guessing is the realistic threat. Previously deferred as D27/L13 pre-prod blocker; it is now the *remaining* blocker. | `accounts/views.py`, `accounts/google_views.py:129-181` (`GoogleLinkConfirmView.post`) | `django-axes` (or nginx-level limit) on `/accounts/login/` + link-confirm; at minimum an attempt counter + lockout on link-confirm. |

---

## 🟡 Medium — SHOULD FIX (fast-follows)

| # | Finding | Where | Fix |
|---|---------|-------|-----|
| **M1** | `mark_fulfilling()` calls `select_for_update()` **without** `@transaction.atomic` — the only `mark_*` missing it. Latent lost-lock; safe today only because its sole caller (`issue_goods`) is atomic. | `orders/services.py:693` | Add `@transaction.atomic`. |
| **M2** | `conn_max_age=0` → no persistent DB connections under gunicorn; every request opens/closes a connection. Safe (no cross-worker reuse, no leaks) but needless latency. | `config/settings/base.py:72` | `CONN_MAX_AGE=60` + `conn_health_checks=True` (health checks only apply when max_age > 0). |
| **M3** | N+1: `warehouse_request_list` → `get_issue_summary()` ≈ 2 queries per line per request; the prefetch on the list is wasted. | `orders/console_views.py` / `inventory/services.py` `_issued_qty_for_line_ids` | Batch the issued-qty lookup by request id once. |
| **M4** | Unbounded lists/feeds: warehouse request list, thread lists, Company Voice `get_feed()`, branch catalog (products/inventory already paginated). | `orders`, `threads`, `company_voice`, `branches` views | Pagination (or at least a cap) before real data volume. |
| **M5** | Google OAuth has **no PKCE** and requires `client_secret`, while the deploy guide registers a "Desktop app" dev client. State param is present (good), but PKCE is cheap and Google-friendly. | `accounts/google_auth.py` | Add `code_challenge`/`code_verifier` (S256) or switch the documented client type to Web app. |
| **M6** | `create_post()` is **not atomic** — the post can persist while its audit `VoiceChangeLog` row fails (every other company_voice mutator is atomic). | `company_voice/services.py:177` | Wrap in `@transaction.atomic`. |
| **M7** | **Session management policy gap (parent finding).** Behavior today: independent per-device sessions (laptop + phone both valid concurrently; logout/expiry per device only; ~14-day non-sliding cookie expiry). No session listing/revocation UI, no idle timeout. Deactivation (`deny_if_inactive`) is the only global kill switch and works correctly. | `config/settings/base.py`, `accounts/authz.py` | Decide the policy and document it; optionally add idle timeout (`SESSION_COOKIE_AGE` + save-every-request) or "log out other devices" (delete other `Session` rows on login). |

---

## 🔵 Low / ⚪ Nit — NICE TO HAVE

- **Unlocked approval-limit reads** (`procurement`/`orders` read `ApprovalLimit`/`BranchApprovalLimit` without lock while another tx may update) — acceptable under read-committed; document or lock.
- **`display_name` email-prefix leak** (Company Voice anonymous display falls back to email prefix) — show a generic label or first name.
- **OAuth `state` not cleared on some error paths** (`google_views.py`) — clear in all branches, not just success.
- **HSTS preload (31,536,000s) enabled before nginx TLS is configured** in the deploy example — ensure 443 + redirect exists *before* enabling preload.
- **No `/healthz`** endpoint for LB/proxy checks.
- **gunicorn: no `--max-requests`** — workers never recycle; add `--max-requests 2000 --max-requests-jitter 200`.
- **`ActiveBranchMiddleware` does a DB query on every request** (`branches/middleware.py`) — cache branch id in session where possible.
- **Empty `config/settings/__init__.py`**, dead code (threads `_bump`, etc. — already recorded as nits N1–N6, not a queue).

---

## ✅ Checked clean (both reviewers, independently)

- **Concurrency:** stock ledger / FIFO reservation / PO snapshot / branch receipt — atomic + `select_for_update` + consistent lock order; no deadlock vector found.
- **`get_or_create` safety:** real `UniqueConstraint` backing `BranchItemStock` (branch,item) and `ThreadReadState` (thread,user); IntegrityError retry in company_voice sub-thread.
- **DB connections:** no raw SQL, no `cursor()`, no manual `connections[]` anywhere → connection leaks are not possible via app code; multi-process-safe file logging (`concurrent_log_handler`).
- **CSRF:** no `csrf_exempt`; all AJAX posts send the token.
- **XSS:** no `mark_safe` / `|safe` / raw `innerHTML`; `feed.js` escapes all user content before rendering.
- **SQL injection:** none (no raw/extra/cursor usage).
- **Mass assignment:** whitelisted fields everywhere.
- **Branch isolation:** other-branch access → 404; capability-based gates (no permissive fallbacks).
- **Admin:** superuser-only `/admin/`.
- **Session fixation:** Django `login()` rotates the session key.
- **Secrets:** prod requires env vars (fail-fast); dev default is clearly dev-only.
- **Migrations:** order sound for a fresh production DB.

---

## Deferred / out of scope (already recorded elsewhere)

- **Phase 6 email automation** — `notify_supplier_on_approval` is a log-only stub; planned next phase. `transaction.on_commit` wiring is already correct.
- **Leftover review nits** (threads N1–N6, Company Voice N1) — recorded, not a work queue.
- **H2 (rate limiting)** was the previously deferred D27/L13 item — this review **promotes it to a ship-blocker**.

---

*Method: parent (main agent) deep pass over settings/auth/middleware/services/deploy/XSS-CSRF surface; subagent independent pass (same scope + performance/resilience/deps/migrations); findings cross-checked line-by-line against the code. Disagreements: none material.*
