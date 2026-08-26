# Code Review — Phase 6 offline catalogue + draft sync + PWA

> **Status (26 August 2026, 10:09 WEST):** **Read-only review — findings recorded, not yet applied.** Parent reviewer + Bugbot subagent; notes merged below.

**Date:** 2026-08-26  
**Reviewers:** parent agent (consistency / failure-point pass) + Bugbot subagent [`ae6939c3`](ae6939c3-3c8f-4ef3-b926-800d4e7f2255)  
**Repo:** `/home/pmpmt/python/260826-central_de_compras/warehouse_V2`  
**Branch:** `main` @ `0b4fb9d`  
**Commits reviewed:** `e531ec8` (branch dashboard + shared nav, PR #18) · `0b4fb9d` (offline catalogue + draft sync + PWA, PR #19)  
**Scope:** Service Worker, IndexedDB, offline requisição draft queue, `InternalRequest.client_uuid`, `POST /api/branch/requests/sync/`, PWA manifest, branch dashboard shell, user manuals §2.4 / Q15–Q16, `DEPLOYMENT.md` HTTPS note.

**Suite at review time:** **533 OK** (commit message; not re-run in this session — venv absent locally).

---

## Summary

Phase 6 delivers the intended MVP: branch app-shell caching, catalogue snapshot in IndexedDB, offline draft requisição with idempotent server sync, and a minimal PWA manifest. PostgreSQL remains the write path; workflow actions (submit / approve) correctly stay online-only. The architecture matches project non-negotiables.

Both reviewers found **reliability gaps in the offline queue and sync contract** — not in the happy path (create draft offline → reconnect on `/branch/requests/` → upload once), but in branch switching, concurrent edits during upload, stuck queue states, and unhandled server exceptions. **No Critical security defect** (tenant isolation on the sync endpoint still flows through `active_branch_required`). **Four High** items should be fixed before treating offline drafts as production-safe for dual-branch users or flaky networks.

---

## Verdict: **ISSUES FOUND — fix High items before production offline rollout**

Phase 6 is **mergeable as dev/MVP** for single-branch users who reconnect on the requisição page. **Not READY for production offline** until H1–H4 and M2 are addressed (wrong-branch sync, stuck queue, line loss on concurrent edit, 500-class sync errors).

---

## Findings (merged)

| # | Sev | Location | Issue | Source |
|---|-----|----------|-------|--------|
| H1 | **High** | `sync_queue.js:9-31`; `branch_requests.js:343-351` | Pending drafts store `branch_id` but `drainQueue` never compares it to the session branch. After switching branch, a North draft can sync onto South. | Both |
| H2 | **High** | `sync_queue.js:39-41,47` | Only `pending` / `failed` entries drain. Crash or navigation mid-sync leaves `syncing` forever — draft never uploads or clears. | Both |
| H3 | **High** | `sync_queue.js:45-53`; `branch_requests.js:287-316` | Drain snapshots the queue entry, POSTs, then `deletePendingRequest`. Lines added to the same draft in IndexedDB while sync is in flight are deleted without being sent. | Both |
| H4 | **High** | `orders/services.py:388-404`; `console_views.py:154-174` | `client_uuid` is globally unique, but idempotency lookup filters `(client_uuid, branch)`. Same UUID on another branch → `save()` raises uncaught `IntegrityError` → **HTTP 500**. | Both |
| M1 | Medium | `requests.html:69-72`; `manifest.webmanifest:5`; `catalog.html` | `BranchSyncQueue.bindAutoSync` runs only on `/branch/requests/`. PWA `start_url` is `/branch/catalog/`, which registers SW but not the sync queue — reconnect on catalogue never drains pending drafts until requisição is opened. | Both |
| M2 | Medium | `orders/services.py:180-183,419-425`; `console_views.py:165-166` | Sync line replay calls `Item.objects.get(pk=…)`. Unknown / deleted `item_id` (stale cache, bad IDB row) → `Item.DoesNotExist` → **HTTP 500** (not caught as `ValidationError`). | Both |
| M3 | Medium | `db.js:35-58`; `branch_catalog.js:65-79`; `branch_requests.js:69-73` | Catalogue cache records `branch_id` in meta but readers never validate it. Dual-membership user who switches branch offline sees the **previous branch's** catalogue and can queue lines against wrong items. | Parent |
| M4 | Medium | `orders/services.py:393-394` | Idempotent replay returns existing request **without merging** `lines` from the payload. Safe today only because create+lines are atomic; any future partial-sync or line-merge change must update this path (documented footgun). | Parent |
| M5 | Medium | `branch_receipts.html`, `branch_threads.html`, `dashboard.html` | Receipts / threads / dashboard include SW shell (or omit it on dashboard) but have **no offline graceful degradation** — cached shell loads, API calls fail with no banner/queue UX. | Parent |
| M6 | Medium | `dashboard.html:27-49` | Branch landing page omits `offline_assets.html` (no manifest link, no `register_sw.js`). First visit after install may not register SW until user navigates to catalog/requests. | Parent |
| L1 | Low | `branch_offline.js:4-6` | `navigator.onLine` is unreliable (desktop “offline” mode, captive portals). False online → failed fetch; false offline → skips sync attempt. | Parent |
| L2 | Low | `db.js:128-142` | `updatePendingRequest` is read-modify-write without transactional isolation — two tabs editing the same pending draft can lose lines. | Parent |
| L3 | Low | Plan vs `orders/urls.py` | [`.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md`](../../.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md) specified replay to existing create/add_line APIs; shipped code uses dedicated `POST …/sync/`. Behaviour OK; docs/plan drift. | Parent |
| L4 | Low | `orders/models.py:67` | Plan said **required** `client_uuid`; model is `null=True` (online `create_internal_request` leaves null). Works, but weakens “UUID everywhere” invariant. | Parent |
| L5 | Low | `branch_requests.js:304-307` | `client_line_uuid` stored in IndexedDB but never sent to server — no line-level idempotency if request-level sync is ever split. | Parent |
| L6 | Low | `service_worker.js:23-28` | Plan listed `/manage/` bypass; `isBypassed` omits it. Low risk (warehouse users rarely hit branch SW). | Parent |
| L7 | Low | `sync_queue.js:57-62` | Failed sync persists `last_error` from `err.message` only — server `code` (e.g. `invalid_client_uuid`) not shown distinctly in UI. | Parent |
| N1 | Nit | `dashboard.html:27` vs branch pages | `settings_menu.css?v=4` on dashboard, `?v=5` elsewhere — minor cache-buster drift. | Parent |
| N2 | Nit | `register_sw.js:8-10` | SW registration failure swallowed silently — no console hint for dev debugging. | Parent |
| N3 | Nit | `service_worker.js:67` | `APP_SHELL.indexOf(url.pathname)` never matches (shell URLs include `?v=` query); dead branch — `/branch/` prefix handles HTML. | Parent |
| N4 | Nit | `orders/tests.py:273-339` | Sync tests cover create, idempotency, inactive item, missing UUID — **no** tests for cross-branch UUID, unknown `item_id`, or `branch_id` queue guard. | Both |
| N5 | Nit | `04-internal-requests.md` Q15 | FAQ implies auto-sync on reconnect globally; actual trigger is opening `/branch/requests/` (or future fix per M1). | Parent |

---

## Detailed notes

### H1 — Wrong branch on sync

`createOfflineRequest` writes `branch_id` from `data-branch-id` (`branch_requests.js:346`). `syncOne` POSTs to `/api/branch/requests/sync/` with **no branch check** — the server uses `request.active_branch` from session only.

**Failure scenario:** User belongs to North and South. Creates offline draft at North. Switches to South (session updated). Opens requisição — queue drains — draft is created on **South** with North item lines.

**Fix direction:** Before POST, skip or fail entries where `entry.branch_id !== document.body.getAttribute("data-branch-id")`; surface “switch back to {branch} to sync”. Server-side: reject sync when `client_uuid` exists on a different branch with **409** + clear code (instead of IntegrityError).

### H2 — `syncing` status stuck

Flow: `updatePendingRequest(…, { status: "syncing" })` → fetch → on success delete; on failure set `failed`. Tab close / browser kill between update and completion leaves `syncing` permanently excluded from `pending.filter` (`sync_queue.js:39-41`).

**Fix direction:** Treat `syncing` as eligible after a timeout, or reset stale `syncing` → `pending` on page load / `drainQueue` start.

### H3 — Concurrent line loss

User selects pending draft, adds a line (writes IDB), while `drainQueue` already snapshot’d an older entry and is mid-POST. Success path calls `deletePendingRequest(client_uuid)` — wipes the row including the new line.

**Fix direction:** Re-read entry from IDB immediately before delete; or use line-level sync with merge; or block UI mutations while `status === "syncing"`; or soft-delete only after verifying server line count ≥ client line count.

### H4 — Cross-branch UUID → 500

```python
existing = InternalRequest.objects.filter(client_uuid=parsed_uuid, branch=branch).first()
if existing is not None:
    return existing, False
# … save() can IntegrityError if UUID exists on another branch
```

**Fix direction:** Lookup by `client_uuid` globally first; if found on other branch → `ValidationError` with code `client_uuid_branch_mismatch` (400). Add test.

### M1 — Sync queue not global

`catalog.html` loads `register_sw.js` via `offline_assets.html` but not `sync_queue.js`. Manifest `start_url` is `/branch/catalog/`. User workflow “go offline → add draft → reconnect on home/catalog” leaves drafts pending until `/branch/requests/` is opened.

**Fix direction:** Move `bindAutoSync` to `register_sw.js` or a shared `branch_init.js` included from `offline_assets.html` (with no-op if `BranchSyncQueue` undefined on non-request pages).

### M2 — Unknown item → 500

`_resolve_item` uses bare `Item.objects.get(pk=item)`. Sync tests cover **inactive** item (validation path) but not missing PK.

**Fix direction:** Wrap in `ValidationError` (“Unknown item id …”, code `unknown_item`) like other service errors.

### M3 — Stale catalogue across branches

`saveCatalog` stores `branch_id` in meta (`db.js:45-48`). `loadFromCache` / offline item picker never compare meta.branch_id to current page branch.

**Fix direction:** On read, if `meta.branch_id !== currentBranchId`, treat as empty cache or force online refresh banner.

### M5 / M6 — Shell without offline UX

Branch dashboard is the post-login landing (`/branch/`) but lacks `offline_assets.html`. Other branch pages precache via SW but receipts/threads JS still assume network — offline visit shows broken tables.

**Fix direction:** (Minimal) include offline banner + “requires Wi-Fi” empty states on non-offline pages; add offline assets to dashboard.

---

## Consistency checks (passed)

| Check | Result |
|-------|--------|
| API routes never cached by SW | Pass — `isBypassed` skips `/api/` |
| Submit / approve / reject disabled offline | Pass — `branch_requests.js:154-188` |
| CSRF on sync POST | Pass — `X-CSRFToken` from meta |
| Branch tenant gate on sync | Pass — `@active_branch_required` |
| Duplicate line on sync payload | Pass — `DuplicateRequestLineError` → 400 |
| Inactive item on sync | Pass — tested |
| Idempotent duplicate POST (same payload) | Pass — tested |
| User manual offline FAQ (Q15–Q16) | Pass — matches draft-only scope |
| `05-edge-cases` sync error strings | Pass — `client_uuid` codes documented |
| SW served with no-cache headers | Pass — `cache_control` on view |
| Warehouse `/manage/` not in offline scope | Pass — no SW registration there |

---

## Test gaps

| Area | Covered | Missing |
|------|---------|---------|
| Sync create + idempotency | Yes | — |
| Sync validation (UUID, inactive item) | Yes | Unknown item_id, cross-branch UUID |
| SW route smoke | Yes | — |
| Frontend queue (IDB, branch guard, syncing reset) | **No** | Manual / future JS tests |
| Offline catalogue fallback | **No** | Manual only (plan slice 1) |
| Multi-tab concurrent pending edit | **No** | — |

---

## Plan of action

Prioritized fix batches — **no new features**, reliability and consistency only.

### Finding → batch map (Medium items)

| Finding | Batch | Plan step | Notes |
|---------|-------|-----------|-------|
| M1 | **P1** | 5 | Global `bindAutoSync` on all branch pages with offline assets |
| M2 | **P0** | 4 | Unknown `item_id` → 500; grouped with High server errors |
| M3 | **P1** | 6 | Validate cached catalogue `branch_id` on read |
| M4 | **Deferred** | — | Idempotent replay skips line merge — safe while create+lines stay atomic; overlaps P0 step 3 if merge-on-replay is chosen for H3 |
| M5 | **P1** | 7 | Offline empty states on receipts / threads |
| M6 | **P1** | 8 | `offline_assets.html` on dashboard |

All **High** findings (H1–H4) map to **P0** steps 1–3 and the M2 fix in step 4.

### P0 — Before production offline (High + M2)

| Step | Fix | Files | Tests to add |
|------|-----|-------|--------------|
| 1 | Validate `entry.branch_id === session branch` before sync; server 400/409 on UUID branch mismatch | `sync_queue.js`, `orders/services.py`, `console_views.py` | Cross-branch UUID; wrong-branch queue entry skipped |
| 2 | Reset stale `syncing` → `pending` on drain start (e.g. &gt; 60s or all syncing on load) | `sync_queue.js`, optionally `db.js` | Manual: kill tab mid-sync, reload |
| 3 | Prevent line loss: re-fetch pending row before delete **or** disable add-line while syncing **or** merge lines server-side on idempotent replay | `sync_queue.js`, `branch_requests.js`, `orders/services.py` | Concurrent add during sync scenario |
| 4 | Catch `Item.DoesNotExist` in sync line path → `ValidationError` / 400 | `orders/services.py` | `test_sync_rejects_unknown_item` |

### P1 — UX reliability (Medium)

| Step | Fix | Files |
|------|-----|-------|
| 5 | Run `bindAutoSync` from shared branch bootstrap (all pages with `offline_assets.html`) | `offline_assets.html`, new tiny `branch_bootstrap.js` or extend `register_sw.js` |
| 6 | Validate cached catalogue `meta.branch_id` on read; clear/warn on mismatch | `branch_catalog.js`, `branch_requests.js` |
| 7 | Add offline banner / “Wi-Fi required” empty state on receipts, threads, dashboard | respective templates + minimal JS |
| 8 | Include `offline_assets.html` on `dashboard.html`; align `settings_menu.css?v=` | `dashboard.html` |

### P2 — Polish + docs (Low / Nit)

| Step | Fix |
|------|-----|
| 9 | Update Q15 if M1 fixed; note dual-branch offline caveat until H1/M3 fixed |
| 10 | Archive plan “replay create/add_line” wording vs shipped `/sync/` endpoint |
| 11 | Consider required `client_uuid` on online create (L4) — optional schema follow-up |
| 12 | Add `/manage/` to SW bypass (L6) |
| 13 | Expand sync tests (N4); document manual offline test recipe in handoff |

### Suggested session order

1. **One PR — “offline sync hardening”:** P0 items 1–4 (backend + queue).  
2. **One PR — “offline UX consistency”:** P1 items 5–8.  
3. **Defer** P2 unless doing a polish slice.

---

## References

- Plan (complete): [`.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md`](../../.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md)  
- Agent rule: [`.cursor/rules/offline-frontend.mdc`](../../.cursor/rules/offline-frontend.mdc)  
- User manual: [`docs/user-manuals/04-internal-requests.md`](../user-manuals/04-internal-requests.md) Q15–Q16  
- Bugbot subagent: [`ae6939c3-3c8f-4ef3-b926-800d4e7f2255`](ae6939c3-3c8f-4ef3-b926-800d4e7f2255)
