# Production deployment readiness — staging HTTP in mind

**Date:** 29 August 2026, 10:25 WEST  
**Repo:** `warehouse_V2` · branch `main`  
**Scope:** full tree as if preparing for production cutover. Existing Contabo staging (`http://169.58.240.120`, no TLS, no Google OAuth) is **accepted**. Google OAuth remains **Phase 8**.  
**Prior review:** 26 Aug 1205 P0/P1/P2 applied — do not re-open unless noted as leftover. Parallel passes: settings/secrets and authz/runtime; extras merged below as L5–L6 and H2/M3 notes.

**Verdict:** current **staging is supported**. **Not ready to promote to real-data production** until backups exist and the public demo/seed-password surface is gated.

| Count | Severity |
|-------|----------|
| 0 | Critical |
| 2 | High |
| 6 | Medium |
| 7 | Low |
| 1 | Nit |

No 1205 P0/P1/P2 regression.

---

## Staging vs production (locked for this review)

| Topic | Staging (today) | Production cutover (Phase 7) |
|-------|-----------------|------------------------------|
| Transport | HTTP, IP-only | Domain + HTTPS (certbot), then `SECURE_SSL_REDIRECT=True` |
| Auth | Password only; Google unset | Still password (`AUTH_MODE=both`). OAuth = Phase 8 |
| Data | Dummy seed, `devpass123` | No `seed_dev_data`; unique passwords; `/admin/` bootstrap |
| PWA / SW | Will not register over HTTP | Works after HTTPS |
| Cookies | `SECURE_COOKIES=False` required | Follow SSL redirect |

---

## Findings

### H1 — High — no PostgreSQL backup / restore discipline

Phase 7 scope in `docs/PROJECT-PLAN.md` includes backups. `docs/DEPLOYMENT.md` and `docs/DEPLOYMENT-CONTABO-STAGING.md` only mention backups as a future DigitalOcean path. There is no `pg_dump` script, cron, restore runbook, or RPO.

Staging loss is painful (demo work). Production without backups is not deploy-ready for stock and requisições.

### H2 — High — public demo surface + ungated seed

`presentation/views.py` hardcodes `DEMO_LOGIN_URL = "http://169.58.240.120/accounts/login/"` and `DEMO_PASSWORD = "devpass123"`. `/presentation/` is unauthenticated and renders both. `seed_dev_data` uses the same password and has **no** `DEBUG` / production guard; the Contabo runbook runs it by design.

**Staging:** accepted for dummy customer demo. **Production:** must not ship the deck with credentials, and must not run seed on a real database (it will reset known users to `devpass123`). `docs/DEPLOYMENT.md` production steps never say “do not seed / disable `/presentation/`” — that omission is part of this finding.

### M1 — Medium — `/admin/login/` is not throttled

DB throttle and nginx `limit_req` cover `/accounts/login/` and `/accounts/google/` only. Django admin login is a separate view. Staging has a superuser on a public IP.

### M2 — Medium — docs still say Phase 7 = Google OAuth

`docs/user-manuals/en/06-admin-reference.md` §12.2 and the production intro in `DEPLOYMENT.md` still bundle Google OAuth into production. The living plan (D35) moved OAuth to Phase 8. Operators may delay HTTPS for the wrong reason.

### M3 — Medium — unbounded lists (1205 M8 leftover)

Warehouse internal-request queue and thread lists are capped at 200. Still full-set: Company Voice `get_feed()`, branch `request_list`, manager catalog, and inventory/PO `_paginate` when `page` / `page_size` are omitted. Fine at seed scale; grows with real use. Branch catalogue dump is intentional for offline.

### M4 — Medium — invalid UTF-8 JSON → 500 on some consoles

`products` / `procurement` / `inventory` `_parse_json` use `request.body.decode()` without catching `UnicodeDecodeError`. Orders, threads, and Company Voice already return 400.

### M5 — Medium — loose dependency pins

`requirements.txt` uses ranges (`Django>=6.1,<7`). Two deploys can resolve different wheels.

### M6 — Medium — `settings_menu.css` cache-buster drift

Warehouse dashboard and Company Voice still use `?v=4`. Branch pages and the Service Worker precache `?v=5`. After a CSS change those two pages keep stale chrome.

### L1 — Low — nginx / systemd hardening gaps

No `proxy_read_timeout` / gzip; gunicorn unit has no `ProtectSystem` / `PrivateTmp` / `NoNewPrivileges`. Bind is correctly `127.0.0.1:8000`.

### L2 — Low — no custom 404/500 templates

`DEBUG=False` still shows Django’s generic safe pages. No traceback leak.

### L3 — Low — throttle records loopback IP

`REMOTE_ADDR` behind nginx is `127.0.0.1`. Username lock still works (1205 M6 prune is applied). Forensics are weak.

### L4 — Low — 403 responses include permission codenames

Authenticated users see strings like `Missing permission: products.add_item`. Dashboard permission dump is correctly gated to superuser / `DEBUG`.

### L5 — Low — nginx sample is not `default_server`

`deploy/centcompras-nginx.conf` uses a domain `server_name`. Staging `sed`s the IP in but does not disable Ubuntu’s default site. If `default` stays enabled, Host-header routing depends on which server wins.

### L6 — Low — `add_item` CLI is ungated

`products/management/commands/add_item.py` mutates the catalogue with `user=None` audit and has no env guard. Lower risk than seed; still a live-DB footgun.

### N1 — Nit — D37 priced mode is company-wide

Flipping Branch commercial settings to priced instantly returns selling prices on every branch client and in the offline cache. Keep **unpriced** unless that is the commercial decision.

---

## Already solid (do not re-open)

- `prod.py`: `DEBUG=False`, `DATABASE_URL` required, SECRET_KEY fail-fast, SSL redirect default false, `SECURE_COOKIES` override, `USE_X_FORWARDED_HOST=False`, HSTS preload off.
- Google button hidden when credentials unset; prod refuses localhost redirect **only if** `GOOGLE_CLIENT_ID` is set.
- CSRF middleware; no `csrf_exempt` / `mark_safe` / raw SQL; no file uploads.
- Superuser-only `/admin/`; branch ↔ warehouse isolation; inactive users refused (password + Google).
- gunicorn `--max-requests`; `/healthz` status-only; login throttle prune; warehouse IR + thread list caps.
- Service Worker `/branch/` HTML network-first; IndexedDB pending rows per user; wipe on sign-out.
- D37 unpriced: branch APIs omit selling prices; offline cache strips price keys.
- Email `notify_supplier_on_approval` remains a log stub (Phase 9).

---

## Suggested act-on order

1. **Staging now:** nightly `pg_dump`; nginx `limit_req` on `/admin/login/`; confirm Ubuntu default site is disabled.
2. **Before real data:** gate `seed_dev_data`; remove or login-gate `/presentation/`; do not copy the Contabo seed step onto production.
3. **HTTPS cutover:** certbot → `SECURE_SSL_REDIRECT=True`; smoke login + one warehouse console + one branch page + `/healthz`.
4. **Cheap same pass:** `settings_menu.css?v=5`; UTF-8 → 400; optional lockfile.
5. **Not this phase:** Google OAuth (Phase 8), shared chrome (Phase 8), real email (Phase 9).
