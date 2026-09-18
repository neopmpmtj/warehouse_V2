---
name: Stability review follow-up (18 Sep 2026)
overview: "Targeted comfort/stability work after the 18 Sep full-tree review. No rewrite. Do not start application patches until a batch is approved."
todos:
  - id: batch-a-offline-idb
    content: "H1 — Filter pending drafts by user_id; wipe or refuse foreign IDB rows on login; hide other users' pending"
    status: pending
  - id: batch-a-pending-discard
    content: "M2/M3 — Discard pending draft + remove pending line; dual-branch skip message"
    status: pending
  - id: batch-a-genesis-retail
    content: "M1 — Server Genesis/activation requires retail_price > 0 (align with console + D29 + D41); update tests/manuals"
    status: pending
  - id: batch-a-demo-gate
    content: "H2 — Gate login/presentation demo passwords (DEBUG or SHOW_DEMO_LOGINS); seed refuse when DEBUG=False"
    status: pending
  - id: batch-a-json-utf8
    content: "M8 — UnicodeDecodeError → 400 on products/procurement/inventory _parse_json (shared helper OK)"
    status: pending
  - id: batch-b-po-cancel-ui
    content: "M6 — Cancelled PO drawer must not headline approved_* as current totals"
    status: pending
  - id: batch-b-subfamily
    content: "M7 — Decide catalog/reactivate vs inactive sub-family; implement the chosen rule"
    status: pending
  - id: batch-b-sip-active-item
    content: "create_supplier_item_price requires active item (manual §4.3)"
    status: pending
  - id: batch-b-css-v
    content: "L5 — settings_menu.css ?v=5 on dashboard + Parle feed"
    status: pending
  - id: batch-b-d37-stale-cache
    content: "M4 — Offline catalog ignores price keys when current mode is unpriced (or meta mismatch)"
    status: pending
  - id: batch-c-docs
    content: "L8 — Sync D29 vs D36/D41; handoff test count 616; issue-after-deactivate FAQ; remove viewBox debug is a separate deck task"
    status: pending
isProject: false
---

# Stability follow-up after 18 Sep 2026 review

**Status:** **Waiting for approval.** Report: [`docs/reviews/code-review-full-2026-09-18-1510.md`](../../docs/reviews/code-review-full-2026-09-18-1510.md).

**Do not implement until a batch is chosen.** This is not a rewrite. Phases 0–6 stay. Architecture stays Django + `services.py` + vanilla JS.

**Bugbot** on clean `main` reported no bugs (no diff). Parent + three domain passes produced the IDs below. Suite at review: **616 OK**.

---

## Recommendation

Approve **Batch A** first (comfort on shared tablets + stop publishing demo passwords + one source of truth for Genesis). Then **Batch B** if you want the remaining consistency traps. **Batch C** is docs-only and can ride with A or B.

Skip a greenfield rewrite. The ledger, FIFO reservation, PO snapshot, and branch isolation are the stable centre.

---

## Batch A — comfort and stability (recommended)

Small, user-visible, low merge risk. Each item is independently shippable if you want to drop one.

### A1. Shared-device pending drafts (H1)

- Filter `loadPending` / `renderList` to `user_id === data-user-id`.
- On branch bootstrap (logged-in), delete pending rows whose `user_id` is missing or not the current user (keep catalogue cache unless you prefer a full IDB wipe on every login).
- Optional extra: wipe IDB on the login page before authenticate (covers “closed tab without Sign out”).
- Tests: document as a JS contract if a Django test cannot see IndexedDB; add a comment in `orders/tests.py` sync suite that server attribution is unchanged.

### A2. Pending discard (M2, M3)

- Button: discard this pending draft (deletes IDB row).
- Remove-line on pending (mirrors server remove-line).
- Dual-branch: if `branch_id` ≠ current, show “this draft belongs to {branch}; switch back or discard” instead of a silent skip.

### A3. Genesis retail on the server (M1)

**Needs a locked-decision confirmation:** treat D29 + console + manuals as source of truth (`retail_price > 0` to activate).

- `validate_item_genesis_ready` requires retail > 0.
- Return code `retail_price_genesis_required` (i18n string already exists).
- Flip `test_console_create_with_zero_retail_price_succeeds_without_supplier` to expect 400 when `activate: true`; inactive create with retail 0 stays allowed.
- `add_item --activate` must pass a retail > 0 (CLI already has `--retail-price`).
- Manuals 01 / 05: state the **server** rule, not only the Genesis dialog.

### A4. Demo credential gate (H2)

- Login demo table and presentation `DEMO_PASSWORD` only when `DEBUG` or explicit `SHOW_DEMO_LOGINS=true`.
- `seed_dev_data` refuses to run when `DEBUG=False` unless `--force` (and log loudly).
- Keep staging Contabo usable via the env flag.

### A5. JSON 400 on remaining consoles (M8)

- Catch `UnicodeDecodeError` like threads/orders already do.
- Prefer one shared helper; do not invent a new app.

---

## Batch B — consistency traps (optional, after A)

- **M6** Cancelled PO: serializer/UI use live zeros or an “approved (historical)” label, keep DB snapshot.
- **M7** Inactive sub-family: either document “catalog still lists the item” or block `reactivate_item` / hide from `get_catalog` when sub-family is inactive. Pick one rule; do not half-mirror family.
- Supplier price create requires active item.
- `settings_menu.css?v=5` on `dashboard.html` and Parle `feed.html`.
- **M4** Offline: if cached `show_selling_prices` is true but the (online) company mode is unpriced, strip price keys when reading the cache. Offline-only mode switch remains best-effort.

---

## Batch C — docs and living truth (cheap)

- PROJECT-PLAN D29: Genesis requires family + **retail > 0**; cost/supplier remain the optional D36 pair.
- Handoff: test count **616**; viewBox debug **is on main**, not “uncommitted”.
- Manual 03/04 FAQ: deactivating an item does not stop warehouse issue of already-approved reservations (L1).
- Presentation TEMP `.viewbox-debug` remains the **existing** next-session deck task, not this stability batch.

---

## Out of scope (do not mix in)

- Phase 7 backups / nginx / gunicorn hardening (own phase).
- Phase 8 `AUTH_MODE=google_only` (M5 can be a one-liner later; default is `both`).
- Splitting `console.js` or `services.py` into packages.
- React / new frontend.
- Re-opening archived 2208 / 1303 / threads nits N1–N6 / Voice N1.

---

## Decision needed from you

Reply with which batches to implement, and for **A3** and **M7** the product rule:

1. **A3:** Server must match the console (retail > 0 to activate) — **recommended** — or keep server permissive and change the manuals.
2. **M7:** Inactive sub-family behaves like inactive family (hide / block reactivate) — or stay “no cascade, item remains listed”.
