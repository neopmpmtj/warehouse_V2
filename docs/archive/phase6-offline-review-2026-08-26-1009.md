# Code Review — Phase 6 offline catalogue + draft sync + PWA

> **Status (26 August 2026, 11:00 WEST):** **Concluded — P0, P1, and P2 applied.** Leftover **L1–L2, L5, L7, N2–N3** nits are recorded in the findings table — **not a work queue**. The Verdict and findings below are the original read-only pass (historical); see **Resolution** for what shipped.

**Date:** 2026-08-26  
**Reviewers:** parent agent (consistency / failure-point pass) + Bugbot subagent [`ae6939c3`](ae6939c3-3c8f-4ef3-b926-800d4e7f2255)  
**Repo:** `/home/pmpmt/python/260826-central_de_compras/warehouse_V2`  
**Branch reviewed:** `main` @ `0b4fb9d` (PRs #18–#19)  
**Fixes applied:** same branch, session 26 Aug 2026 (uncommitted)  
**Scope:** Service Worker, IndexedDB, offline requisição draft queue, `InternalRequest.client_uuid`, `POST /api/branch/requests/sync/`, PWA manifest, branch dashboard shell, user manuals §2.4 / Q15–Q17, `DEPLOYMENT.md` HTTPS note.

**Suite at review time:** **533 OK**. **Suite after fixes:** **540 OK** (26 Aug 2026).

---

## Resolution (26 Aug 2026)

| Batch | Status | Summary |
|-------|--------|---------|
| **P0** (H1–H4, M2) | ✅ Applied | Branch guard on sync queue; stale `syncing` reset; concurrent line loss prevented; cross-branch UUID + unknown item → 400 |
| **P1** (M1, M3, M5, M6) | ✅ Applied | `branch_bootstrap.js` global auto-sync; catalogue `branch_id` validation; offline empty states; dashboard offline assets |
| **P2** (steps 9–13) | ✅ Applied | Manuals Q15–Q17; plan “shipped vs planned” note; SW `/manage/` bypass; expanded sync tests; manual recipe in handoff |
| **M4** | ⏸ Documented | Idempotent replay does not merge lines — safe while sync stays atomic |
| **L4** | ⏸ Optional | Required `client_uuid` on online create — schema follow-up only; not blocking |

**Verdict after fixes:** Phase 6 offline is **production-ready for branch draft sync** within documented limits (draft-only offline; submit/approve online; dual-branch users must sync on the branch where the draft was created).

---

## Summary (original)

Phase 6 delivers the intended MVP: branch app-shell caching, catalogue snapshot in IndexedDB, offline draft requisição with idempotent server sync, and a minimal PWA manifest. PostgreSQL remains the write path; workflow actions (submit / approve) correctly stay online-only.

Both reviewers found **reliability gaps in the offline queue and sync contract** — not in the happy path, but in branch switching, concurrent edits during upload, stuck queue states, and unhandled server exceptions. **No Critical security defect.**

---

## Verdict (original): **ISSUES FOUND**

Historical — see **Resolution** above.

---

## Findings (merged)

| # | Sev | Location | Issue | Applied |
|---|-----|----------|-------|---------|
| H1 | **High** | `sync_queue.js`; `branch_requests.js` | Wrong-branch sync after branch switch | ✅ P0 |
| H2 | **High** | `sync_queue.js` | `syncing` stuck forever | ✅ P0 |
| H3 | **High** | `sync_queue.js`; `branch_requests.js` | Line loss during in-flight sync | ✅ P0 |
| H4 | **High** | `orders/services.py` | Cross-branch UUID → 500 | ✅ P0 |
| M1 | Medium | templates / manifest | Auto-sync only on requisição page | ✅ P1 |
| M2 | Medium | `orders/services.py` | Unknown item → 500 | ✅ P0 |
| M3 | Medium | `db.js`; catalogue readers | Stale catalogue across branches | ✅ P1 |
| M4 | Medium | `orders/services.py` | Idempotent replay skips line merge | ⏸ Documented |
| M5 | Medium | receipts / threads / dashboard | No offline degradation | ✅ P1 |
| M6 | Medium | `dashboard.html` | No offline assets on landing | ✅ P1 |
| L1 | Low | `branch_offline.js` | `navigator.onLine` unreliable | Recorded |
| L2 | Low | `db.js` | Multi-tab RMW race on pending draft | Recorded |
| L3 | Low | Plan vs shipped | `/sync/` vs replay create/add_line | ✅ P2 plan note |
| L4 | Low | `orders/models.py` | Nullable `client_uuid` online | ⏸ Optional |
| L5 | Low | `branch_requests.js` | `client_line_uuid` unused server-side | Recorded |
| L6 | Low | `service_worker.js` | `/manage/` not in bypass | ✅ P2 |
| L7 | Low | `sync_queue.js` | Server error `code` not in UI | Recorded |
| N1 | Nit | `dashboard.html` | `settings_menu.css?v=` drift | ✅ P1 |
| N2 | Nit | `register_sw.js` | SW failure silent | ✅ P2 (`console.warn`) |
| N3 | Nit | `service_worker.js` | Dead `APP_SHELL.indexOf` branch | Recorded |
| N4 | Nit | `orders/tests.py` | Missing sync edge tests | ✅ P2 |
| N5 | Nit | Q15 FAQ | Auto-sync scope wording | ✅ P2 |

---

## Manual offline smoke test

Use **`http://127.0.0.1:8000`** consistently (not mixed with `localhost`).

1. Seed / log in as `branch.manager.north@centcompras.dev` (`devpass123`).
2. Visit `/branch/catalog/` online — confirm table loads (catalogue cached to IndexedDB).
3. DevTools → Application → Service Workers — confirm `/service-worker.js` registered.
4. DevTools → Network → **Offline**.
5. Open `/branch/requests/` — **New request**, add a line from cached catalogue; list shows **pending sync**.
6. Network → **Online** — open `/branch/catalog/` or `/branch/` (bootstrap auto-sync) — pending draft uploads; refresh requisição list shows server draft.
7. **Dual-branch:** user with North + South — create offline draft at North, switch to South — draft stays pending (not synced to South); switch back to North — draft syncs.
8. **Branch catalogue:** switch branch offline without refresh — catalogue shows branch-mismatch message (not the other branch's items).

---

## References

- Plan: [`.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md`](../../.cursor/plans/phase_6_branch_offline_c0798b8a.plan.md)  
- Agent rule: [`.cursor/rules/offline-frontend.mdc`](../../.cursor/rules/offline-frontend.mdc)  
- User manual: [`docs/user-manuals/04-internal-requests.md`](../user-manuals/04-internal-requests.md) Q15–Q17  
- Bugbot subagent: [`ae6939c3-3c8f-4ef3-b926-800d4e7f2255`](ae6939c3-3c8f-4ef3-b926-800d4e7f2255)
