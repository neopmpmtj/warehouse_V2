# Code Review — full tree, stability (`main` @ `6674303`)

> **Status (18 September 2026, 16:10 WEST):** **Read-only.** No application code was changed. A proposed follow-up plan is in [`.cursor/plans/stability_review_followup_2026_09_18.plan.md`](../../.cursor/plans/stability_review_followup_2026_09_18.plan.md). **Do not treat this report as a work queue until the batches in that plan are approved.**

**Date:** 2026-09-18  
**Repo:** `/workspace`  
**Branch reviewed:** `main` @ `6674303` (clean, in sync with `origin/main`)  
**Suite at review time:** **616 OK** in 21.4s  
`.venv/bin/python manage.py test products accounts procurement inventory branches orders threads company_voice --noinput`

**Scope:** entire live warehouse system after Phases 0–6 plus later slices (D32 FIFO, D37 commercial mode, D38 chrome, D41 retail snapshot, presentation deck). Goal: dead ends, traps, logic flaws, and whether a rewrite is justified. Comfort and stability over speed; low user volume.

**Not in scope as a work queue:** archived 2208 / 1303 findings (applied); leftover nits already recorded in `docs/handoff.md` unless they have grown into real traps; Phase 8 OAuth product work.

---

## How this review was done

| Reviewer | Scope | Method |
|----------|--------|--------|
| Parent (this document) | Full tree | Independent read of services, state machines, offline client, login/demo surface, Genesis vs D29/D41; verified every sub-agent finding against current code |
| Inventory + orders explorer | D32 FIFO, D31/D42 receipts, request FSM | Read-only pass of `inventory/services.py`, `orders/services.py`, tests |
| Catalogue + procurement explorer | Genesis, PO FSM, D12–D16 | Read-only pass of `products/services.py`, `procurement/services.py` |
| Offline / auth / tenancy explorer | Phase 6 IDB, D37, OAuth, threads/voice | Read-only pass of SW, `sync_queue.js`, `db.js`, `authz.py` |
| Bugbot | Asked for full-tree stability | Returned **no bugs**. Expected: Bugbot is diff-oriented and `main` had an empty working tree. It is **not** a clean bill of health. |

Disagreements were resolved by parent verification. Unified IDs below are the ones to consider.

**Already applied — do not re-open** unless an ID below says it is still broken: 2208 P0–P4; 1303 N1–N12; threads M1–M5 / L1–L6; Company Voice H1 / M1–M9 / L1–L8; chrome H1–H3 / M1 / L1 / L2; 24 Aug production-readiness; Phase 6 offline P0 / P1 / P2; 26 Aug 1205 P0 / P1 / P2; D37 H1 / M1 / M2 / L1–L3 and deep-review leftovers.

---

## Summary

The warehouse **core is sound**. Mutations still go through `services.py`. Stock cannot go negative on the ledger path. FIFO reservation (D32), PO approved-totals snapshot (D13), branch 404 isolation, and `select_for_update` + item pk lock order are coherent and well tested. **Do not rewrite the application.** A greenfield rebuild would throw away the part that is already stable.

What is not solid is the **edges staff will hit on a shared tablet or a first production day**:

1. Offline drafts still live in a **device-wide** IndexedDB. Sign-out wipes it (1205 H2). **Login does not.** Another user on the same browser can see and edit the previous operator’s pending requisição.
2. **Demo passwords are hardcoded** on the public login page and the unauthenticated presentation deck. Seed has no production guard. This is still the 29 Aug Phase 7 H2 finding.
3. **Genesis is split-brain.** The item console, manuals, and D29 say selling price must be > 0 to activate. The server and CLI do not enforce that. D41 then rejects the same item on a branch requisição.
4. Failed offline drafts have **no discard path** — a real dead end for branch staff.

No Critical security defect was found (no warehouse rights leaking to a branch-only user; CSRF on POSTs; `/api/` never cached by the Service Worker).

---

## Verdict: **ISSUES FOUND — core stable, edges not comfortable**

Suitable to keep building **warehouse operations** on. Not comfortable as a shared-tablet / internet-facing production system until **Batch A** in the follow-up plan is approved and applied. A rewrite is **not** recommended.

| Count | Severity |
|-------|----------|
| 0 | Critical |
| 2 | High |
| 8 | Medium |
| 8 | Low |
| 3 | Nit |

---

## Findings (unified)

### High

#### H1 — Shared device: IndexedDB pending drafts leak across logins

**Where:** `orders/static/orders/js/branch_requests.js` (`loadPending` / `renderList` / `addLine`); `branches/static/branches/js/sync_queue.js` (`isWrongUser`); `branches/static/branches/js/offline_logout.js`; `branches/static/branches/js/db.js`

**What happens.** Pending requisições are stored in origin-scoped IndexedDB `centcompras_branch`. Sign-out deletes the database. Login does not. `loadPending()` lists **every** row; it does not filter `user_id`. Auto-sync skips the other user’s rows (`isWrongUser`), so they are not uploaded as the new operator — but the new operator **sees the lines** and can **add lines** to that local draft. When the original operator signs back in, their pending draft has been mutated.

**Why it matters.** Branch tablets are the realistic PWA deployment. 1205 H2 closed the sign-out path; this is the remaining “closed the browser / switched user without Sign out” path.

**Reproduction sketch.** Operator A creates an offline draft on Norte. A closes the tab without Sign out. Operator B logs in on the same browser → `/branch/requests/` shows A’s pending UUID. B can open it and add a line. A later signs in; the extra line is still in IDB.

**Tests.** Server sync tests cover idempotency and cross-branch UUID. **No** shared-device / `user_id` mismatch UI test.

**Not a regression of auto-sync attribution** (drain still skips wrong user). It is a privacy + local-mutation trap.

---

#### H2 — Public demo credentials + ungated seed (Phase 7 leftover, still live)

**Where:** `accounts/templates/accounts/login.html` (unconditional `devpass123` table); `presentation/views.py` (`DEMO_PASSWORD`, `DEMO_LOGIN_URL`); `products/management/commands/seed_dev_data.py` (`DEFAULT_PASSWORD`, no `DEBUG` / production guard)

**What happens.** Anyone who can open `/accounts/login/` or `/presentation/` sees every seed email and the shared password. `seed_dev_data` will reset those users to `devpass123` on a real database.

**Why it matters.** Comfort/stability for a low-volume warehouse still requires that the login page not publish passwords if the host is reachable. Documented as Phase 7 H2 on 29 Aug; **not applied**. Staging-with-dummy-data can keep this; production must not.

**Reproduction.** Open `/accounts/login/` while logged out. The demo table is in the HTML with no `DEBUG` gate.

**Tests.** `accounts.tests` asserts the password is present. Presentation tests assert the deck contains `DEMO_PASSWORD`.

---

### Medium

#### M1 — Genesis split-brain: UI requires retail > 0, server does not

**Where:** `products/static/products/js/console.js` `isGenesisReady()` (family + `retail > 0`); `products/services.py` `validate_item_genesis_ready` (no retail check); `products/console_views.py` create with `activate: true`; `products/management/commands/add_item.py`; i18n key `retail_price_genesis_required` (never returned by the server)

**What happens.** Staff using the console get an inactive item when selling price is 0 — matching manuals (`01-items.md`) and locked D29. API/CLI/`create_and_activate_item` can activate with `retail_price=0`. That item appears in the catalogue. Branch `add_line` / `submit` / `approve` then fail with D41 `Item 'X' has no selling price.`

**Why it matters.** Two sources of truth for “this item is sellable”. Console users are mostly protected; seed/CLI/API are not. Staff will not understand why an **active** catalogue row cannot be requested.

**Reproduction.** `POST /api/manage/items/` with `activate: true` and `retail_price: "0"` (covered as success today: `test_console_create_with_zero_retail_price_succeeds_without_supplier`). Then branch add-line → `retail_price_missing`.

**Recommendation.** Treat D29 + D41 as one rule: **Genesis/activation requires `retail_price > 0` on the server**, matching the console. Keep inactive drafts with retail 0. Confirm before coding — tests currently encode the opposite.

---

#### M2 — Offline pending drafts have no discard / remove-line path

**Where:** `orders/static/orders/js/branch_requests.js` (`renderPendingDetail`, `addLine`; `removeLine` only hits the server API)

**What happens.** A pending IDB draft can gain lines but cannot drop a line or delete the draft. If sync fails (`inactive_item`, `retail_price_missing`, unknown item), the row stays `failed` until someone clears site data.

**Why it matters.** This is a **user-visible dead end**. Dual-branch skips (M3) make it worse.

**Reproduction.** Cache catalogue → warehouse deactivates the item → go online → sync fails → pending remains; no button to throw it away.

---

#### M3 — Dual-branch pending rows are skipped forever with no UI

**Where:** `branches/static/branches/js/sync_queue.js` `isWrongBranch`; manuals 04 Q15 (documented skip)

**What happens.** A Norte offline draft is listed (H1 also lists it) while the session is on Sul. Auto-sync skips it until the user switches back. There is no “this belongs to Norte — switch or discard” affordance.

**Why it matters.** Dual users (`filial.dual`) are in the seed. Documented behaviour is easy to miss in the console.

---

#### M4 — D37: stale priced catalogue cache after switching to unpriced

**Where:** `branches/static/branches/js/db.js` `saveCatalog` / `getCachedCatalog`; `orders/static/orders/js/branch_requests.js` pending estimate

**What happens.** Prices are stripped only when **saving** a new snapshot with `show_selling_prices !== true`. If the company switches to unpriced while a tablet stays offline, the last priced snapshot still has price keys and `meta.show_selling_prices === true`.

**Why it matters.** Server APIs are correct. The leak is **offline-only**, until the next online catalogue fetch.

---

#### M5 — `AUTH_MODE=google_only` without Google credentials still accepts password POST

**Where:** `accounts/views.py` `LoginView.dispatch`; `accounts/templates/accounts/login.html` (`{% if auth_mode != "google_only" %}` hides the form)

**What happens.** When Google env is empty, dispatch logs an error and **falls through** to Django’s password `LoginView`. The template hides the form, but a POST to `/accounts/login/` still authenticates. When Google **is** configured, dispatch redirects before `super().dispatch` — that path is correct.

**Why it matters.** Phase 8 cutover trap, not today’s `AUTH_MODE=both` default. Fail-open vs the documented “password login is then disabled”.

**Tests.** `test_google_only_mode_without_credentials_shows_message` checks GET text, not that POST is rejected.

---

#### M6 — Cancelled approved PO still headlines frozen approved money

**Where:** `procurement/services.py` `cancel()`; `procurement/console_views.py` serializer; `procurement/static/procurement/js/purchase_orders.js` (uses `approved_*` whenever present)

**What happens.** Cancel after approve (no receipts) is allowed and tested. `approved_net/vat/gross` stay populated for audit. The drawer still shows those figures as the live totals under status Cancelled.

**Why it matters.** Audit fields should stay. Displaying them as the current total is the trap.

---

#### M7 — Inactive sub-family is weaker than inactive family

**Where:** `products/services.py` `get_catalog` (filters `family__is_active`, not `sub_family__is_active`); `reactivate_item` (family active + Genesis only)

**What happens.** D16 no-cascade is locked and tested (`test_deactivate_sub_family_does_not_deactivate_items`). Items remain in the manager catalog under an inactive sub-family. `reactivate_item` can turn an item active while its sub-family is inactive. Assign-on-create still uses `_ensure_sub_family_usable`.

**Why it matters.** Asymmetry vs family (inactive family drops the item from `get_catalog`). Either document it as locked or mirror the family rule on reactivate.

---

#### M8 — Invalid UTF-8 JSON still 500s on catalogue / PO / goods-receipt consoles

**Where:** `products/console_views.py`, `procurement/console_views.py`, `inventory/console_views.py` — `_parse_json` uses `request.body.decode()` without `UnicodeDecodeError`. Orders / threads / Company Voice already return 400.

**What happens.** Garbage bytes → 500 instead of 400 `invalid_json`. Phase 7 review M4, still open. Low traffic, but it is an uncaught exception on staff consoles.

---

### Low

#### L1 — `issue_goods` does not re-check item activity

Submit/approve block inactive items. After approve, warehouse can still issue (D32 reservations persist). Often **correct** (physical stock still on the shelf). Trap only if staff believe Deactivate = stop shipping. Prefer a manual note over a hard block (a hard block would stick reserved qty).

#### L2 — Submitted requisição cannot be withdrawn

Only `approved`/`rejected`. Documented in manual 04. Same shape as submitted POs. Not a missing transition; operators must ask a manager to reject.

#### L3 — Manager catalog `available` annotation is unclamped

`annotate_item_reservations` uses `F("quantity") - F("reserved")`. Service `available_quantity()` floors at 0. Only visible if the reserved ≤ on-hand invariant is already broken (admin/shell).

#### L4 — `quantity_reserved` not zeroed on terminal statuses

`reserved_quantity()` only sums `approved`/`fulfilling`, so availability is correct. Orphan numbers on `closed`/`cancelled` confuse audits.

#### L5 — `settings_menu.css?v=4` vs `?v=5`

Warehouse dashboard and Parle feed still pin `v=4`. Branch SW precache is `v=5`. Same class of cache-buster drift as the 24 Aug empty-catalog incident, limited to chrome CSS on two pages.

#### L6 — Draft PO lines freeze unit cost / VAT at add-line

Correct after submit (D13). While still draft, a later supplier-price edit does not refresh the line unless the user edits it.

#### L7 — `threads.services._bump` is unused

Recorded threads N1. Harmless dead helper.

#### L8 — Living docs drift

Handoff still quotes **548** tests (26 Aug) and says viewBox debug is “uncommitted”; it is **on `main`**. PROJECT-PLAN D29 still says Genesis needs retail + cost > 0; D36 already made cost optional and the server never required retail. Agents following D29 will “fix” the wrong layer.

---

### Nit

#### N1 — `_parse_decimal_quantity` name

Quantities are integers after `inventory/0004_integer_quantities`. Misleading name only.

#### N2 — Unbounded Company Voice feed

Recorded CV N1. Fine at seed scale.

#### N3 — Unknown `?status=` on warehouse threads → empty list

Recorded threads N6.

---

## What looks scary but is correct

| Topic | Why it is not a bug |
|-------|---------------------|
| Request `shipped` until the branch receives | D42 / D31. Warehouse queue hides it. Branch receive or branch short-close are the exits. |
| `fulfilling` blocks branch short-close | Warehouse may still dispatch. Warehouse short-close is the escape. Tested. |
| Approve never fails for lack of stock | D32 R12. Remainder is backorder; FIFO on incoming stock. |
| Unpriced mode still stores `unit_price` / `approved_*` | D41 warehouse Gross. Hidden from branch JSON. |
| Receive against a PO after item/supplier deactivate | D16: in-flight lines may still be fulfilled. |
| Rejected requisição is terminal | Manual 04: raise a new one. |
| Cancel approved PO leaves `approved_*` in the DB | Audit snapshot; the bug is UI (M6), not the freeze. |
| One primary supplier price | Item row lock + partial unique. Races covered. |
| Offline `client_uuid` uniqueness | Cross-branch mismatch 400; concurrent create upserts. |

Request status exits that exist today:

```text
draft → submitted | cancelled
submitted → approved | rejected
approved → cancelled | fulfilling | shipped | closed
fulfilling → shipped
shipped → received | closed
received → closed
```

No extra legal exit is missing for the locked product rules. Operational stalls (`shipped` waiting on the branch, `received` PO waiting on short-close) are **backlog**, not code dead-ends.

---

## Test gaps worth adding (if a fix batch is approved)

1. Shared device: user A pending visible/editable after user B login; drain must not attribute to B.
2. Genesis `activate=true` with `retail_price=0` → 400 once M1 is aligned (today this test asserts 200).
3. Pending discard after `inactive_item` sync failure.
4. `AUTH_MODE=google_only` without credentials → password POST  rejected.
5. Cancelled PO serializer does not present approved totals as current money.
6. `receive_goods` + FIFO allocation (adjust-up is covered; receipt path shares the helper but has no direct test).
7. Reactivate item while sub-family inactive.

---

## Refactoring — recommendation (do not start from scratch)

A rewrite would re-implement the ledger, FIFO, PO snapshot, and tenancy for little gain. The architecture (`views → services.py → models → PostgreSQL`) is the right shape for this domain and this team.

If we **were** starting today, we would still choose Django + service layer + vanilla JS. We would **not** choose a SPA. Differences worth taking incrementally, not as a big-bang:

| Idea | Why | When |
|------|-----|------|
| One `validate_item_genesis_ready` that matches the console (retail > 0) | M1 split-brain | Batch A |
| Shared `_parse_json` / `_parse_int_id` in one module | Unicode 500s (M8); copy-paste across 5 apps | Batch A/B |
| IndexedDB key or filter by `user_id` from day one | H1 | Batch A |
| Demo credentials compiled out unless `DEBUG` / `SHOW_DEMO_LOGINS` | H2 | Batch A (or Phase 7) |
| Split `products/static/products/js/console.js` (~2700 lines) into item / family / supplier modules | Maintainability only | Optional later; bump every `?v=` |
| Split giant `products/services.py` / `inventory/services.py` into packages | Navigation | Optional; high merge risk, low user value |

**Do not** extract a new framework, add React, or merge apps. Comfort comes from closing the traps above, not from a new folder layout.

---

## Comparison with prior reviews

| Prior ID | Still open? |
|----------|-------------|
| 1205 H2 (IDB wipe on logout + per-user `user_id` on drafts) | **Partially.** Logout wipe and `user_id` field exist. List/filter/login-wipe do not. This review’s H1. |
| Phase 7 (29 Aug) H1 backups | Unchanged — Phase 7. |
| Phase 7 H2 demo credentials | **Yes — this H2.** |
| Phase 7 M4 UTF-8 JSON | **Yes — this M8.** |
| Phase 7 M6 CSS `?v=` | **Yes — this L5.** |
| Threads N1 `_bump` | **Yes — this L7.** Recorded nit. |
| D37 leftovers | Applied; remaining edge is offline stale cache (M4). |

---

## Proposed next step

See [`.cursor/plans/stability_review_followup_2026_09_18.plan.md`](../../.cursor/plans/stability_review_followup_2026_09_18.plan.md). **No application patch until a batch is approved.**
