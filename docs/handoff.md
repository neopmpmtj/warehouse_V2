# CentCompras — Session Handoff

> **Read this first when resuming work.** Last updated: 24 August 2026, 11:20 WEST.

---

## TL;DR — where we are

| Phase | Status |
|-------|--------|
| 0 — Auth + catalogue identity + staff console | ✅ Done |
| 1 — Pricing (selling prices + supplier price list) | ✅ Done |
| 2 — Procurement (purchase orders) | ✅ Done |
| **3 — Goods receipt + stock ledger** | ✅ **Done** |
| **4 — Manager catalog (stock + price view)** | ✅ **Done** |
| 5 — Branches + internal request | ✅ **Done** |
| 5+ — Item `internal_code` constraints | ✅ **Phase 1 + 2 done** |
| 5+ — Sub-families (`FamilyProduct` → `SubFamily`) | ✅ **Done** |
| 5+ — Warehouse FIFO stock reservation (D32) | ✅ **Done** |
| 5+ — Request threads (catalogue-gap requests) | ✅ **Done** (reviewed 24 Aug) |
| 5+ — Request threads review fixes (M1–M5, L1–L6) | ✅ **Done** |
| 5+ — Company Voice (suggestion box) | ✅ **Done** (reviewed 24 Aug) |
| 5+ — Company Voice review fixes (H1, M1–M9, L1–L8) | ✅ **Done** |
| 6 — Email automation | 🔵 **Next** |
| 7 — Mobile / offline / PWA / OAuth | ⏸ Future |

**Phases 0–5, item `internal_code` Phases 1–2, the sub-families catalogue slice, warehouse FIFO reservation (D32), request threads, Company Voice, the 24 Aug threads-review M/L fixes, and the Company Voice review H1/M/L fixes are complete.** **Next session: Phase 6 — email automation** ([`docs/PROJECT-PLAN.md`](PROJECT-PLAN.md) §13).

**Full suite green (502 tests).**

---

## Next session — do this

1. **Phase 6 — email automation** — wire `notify_supplier_on_approval` (and any other stubs) to real email (SMTP/provider); templates EN + pt-PT; audit sent notifications. See [`docs/PROJECT-PLAN.md`](PROJECT-PLAN.md) §13.
2. **Do not start** offline, shared chrome, or server-side item drafts without a plan (drafts deferred per D30).
3. **Do not treat as a work queue:** archived reviews (1303, 2208, sub-family stitch-in) and leftover **nits** from the 24 Aug reviews. Those findings are **recorded**, not Next. See [Recorded leftover nits](#recorded-leftover-nits-not-a-work-queue).
4. Recreate the test DB **without** `--keepdb` if it goes stale after schema changes (`company_voice/migrations/0002_edited_at_and_changelog.py`).

---

## Recorded leftover nits (not a work queue)

The 24 Aug reviews kept their Nit findings so they are not discarded. **Do not start a session to apply these** unless someone asks for a dedicated polish slice.

| Review | Still leftover | Applied with the M/L pass |
|--------|----------------|---------------------------|
| Request threads ([report](reviews/threads-review-2026-08-24.md)) | **N1–N6** — unused `_bump` / `for_user_branches` / `read_attr`; warehouse page catalog call; mixed `hidden` vs class; unbounded thread list; silent double-close; unknown `?status=` → empty set | M1–M5, L1–L6 |
| Company Voice ([report](reviews/company-voice-review-2026-08-24-1010.md)) | **N1** — unbounded feed (already deferred in `09-company-voice.md` FAQ) | H1, M1–M9, L1–L8, **N2** (tag allow-list), **N3** (`filter().first()` on sub-thread) |

---

## This session (24 Aug 2026) — Company Voice review fixes ✅

- **Applied:** H1, M1–M9, L1–L8, N2, and N3 from [`docs/reviews/company-voice-review-2026-08-24-1010.md`](reviews/company-voice-review-2026-08-24-1010.md). **N1** (unbounded feed) remains recorded, not a queue.
- **H1:** `edited_at` set only on real edits; create API `edited: false`.
- **M1:** invalid JSON / non-object body → **400** `invalid_json`.
- **M2:** `select_for_update` on the post for delete/comment; `IntegrityError` savepoint on first-comment `get_or_create`; concurrent tests.
- **M3:** PATCH requires `updated_at`; mismatch → **409** `stale_edit`.
- **M4/M5:** failed writes reload the feed; `renderFeed()` restores comment drafts.
- **M6:** `comment_count` is live comments only.
- **M7:** admin inspect-only (no hard delete).
- **M8:** `VoiceChangeLog` (created / edited / deleted). Migration `company_voice/0002_edited_at_and_changelog.py`.
- **M9:** **Refresh** button on `/company-voice/`.
- **L1–L8:** boolean `is_anonymous`; double-submit lock; client edit-window expiry; i18n `code` map; quote-escaping; `tag: null` clears; `cc-lang` + `{% static %}` + Escape-to-cancel; pt-PT **Anónimo**.
- **Tests:** +13 → **502** total.
- **Manuals:** [`09-company-voice.md`](user-manuals/09-company-voice.md), [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md) §2.6, [`06-admin-reference.md`](user-manuals/06-admin-reference.md).

---

## Earlier this session (24 Aug 2026) — Company Voice review

- **Method:** two sub-agents in parallel (backend; frontend + live API) + independent parent pass; notes compared.
- **Report:** [`docs/reviews/company-voice-review-2026-08-24-1010.md`](reviews/company-voice-review-2026-08-24-1010.md).
- **Verdict:** **ISSUES FOUND** — no Critical; **1 High, 9 Medium, 8 Low, 3 Nit**.
- **H1:** every new post/comment is serialized `edited: true` (`updated_at > created_at` by microseconds on insert). Confirmed in PostgreSQL.
- **M1–M9:** invalid JSON → 500; parent-delete vs first-comment race (no `select_for_update`); last-write-wins PATCH; failed writes leave stale UI; `renderFeed()` innerHTML wipes drafts; `comment_count` includes tombstones; admin hard-delete still enabled; no ChangeLog; shared feed never refreshes other users.
- **Do not implement in this session** — report only. **Applied later the same day** (H1, M1–M9, L1–L8).

---

## Earlier this session (24 Aug 2026) — request-threads review fixes ✅

- **Applied:** M1–M5 and L1–L6 from [`docs/reviews/threads-review-2026-08-24.md`](reviews/threads-review-2026-08-24.md). Nits N1–N6 left as-is (not blocking Phase 6).
- **M1/M2:** non-string JSON and `?branch_id=abc` return **400** (not 500).
- **M3:** list/detail prefetch `read_states` + `items`; `is_unread_for` uses the prefetch cache (query count does not grow with N).
- **M4:** `selectThread` hides close/link dialogs so confirm cannot hit the wrong thread.
- **M5:** override close stores `satisfaction=None` (opener-only rating); close dialog hides stars on override. Migration `threads/0003_satisfaction_nullable.py`.
- **L1:** `link_items` rejects unknown ids; re-link skips a duplicate changelog row.
- **L2:** GET detail no longer marks read; explicit POST `…/mark-read/` (list click). Page-load preview does not clear the unread badge.
- **L3:** branch empty-state hides once threads exist.
- **L4:** item search uses `@warehouse_threads_required` + `@require_GET` (anonymous **401**).
- **L5:** `create_thread` requires the opener to be a member of the branch.
- **L6:** satisfaction rejects bools and non-ints (`True`, `3.7`).
- **Tests:** +10 → **489** total.
- **Manuals:** [`08-request-threads.md`](user-manuals/08-request-threads.md), [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md) §2.5.

---

## Earlier this session — Company Voice app ✅

- **App:** `company_voice` — company-wide suggestion box at `/company-voice/` (all logged-in staff).
- **Models:** `VoicePost` (optional tag, anonymous flag), `VoiceSubThread` (one per post), `VoiceComment`.
- **Rules:** 15-minute edit window; creator-only soft delete; parent delete cascades to sub-thread + comments; `[Deleted by author]` placeholder.
- **UI:** Single scrollable feed; inline reply panel; EN + pt-PT i18n.
- **Tests:** `company_voice.tests` (+18) → **479** total.
- **Manual:** [`09-company-voice.md`](user-manuals/09-company-voice.md).

---

## This session (24 Aug 2026) — request-threads review

- **Reviewer:** DeepSeek Flash sub-agent (read-only; no source modified).
- **Report:** [`docs/reviews/threads-review-2026-08-24.md`](reviews/threads-review-2026-08-24.md).
- **Verdict:** **ISSUES FOUND** — no Critical/High; **5 Medium, 6 Low, 6 Nit**. Full suite **461 tests OK** (41.4s).
- **M1–M5 (Medium):** non-string JSON → 500 (`services.py:97,129,133`); `?branch_id=abc` → 500 (`console_views.py:225`); N+1 list queries (dead prefetch, `models.py:108–116`); stale dialogs on thread switch → wrong-thread close/link (both templates); override close stamps the opener's satisfaction (`services.py:279–341`).
- **L1–L6 (Low):** `link_items` silently accepts nonexistent item IDs; page-load auto-mark-read (GET side-effect); branch empty-state stays visible; lighter gate on `search_items_for_link`; `create_thread` no membership check; satisfaction coercion (`3.7→3`, `True→1`).
- **N1–N6 (Nit):** dead code (`_bump`, `for_user_branches`, `read_attr`); pointless catalog call on warehouse page; mixed visibility patterns; no pagination; silent double-close; unrecognized `?status=` → empty set.
- ⚠️ **M1–M5 and L1–L6 applied 24 Aug (afternoon).** Leftover **N1–N6 nits** are optional and do **not** block Phase 6.

---

## This session (23 Aug 2026) — landed

### Request threads (catalogue-gap requests) ✅

- **Feature:** a branch opens a written **thread** (subject + free-text first message) when the needed item does **not** exist in the `Item` table. Warehouse engages; back-and-forth until understood; warehouse creates the item via the item console; **only the opener closes** (reason required: default "Request Satisfied" / "Other" + text). Branch manager/admin + warehouse admin can force-close (override).
- **App:** `threads` — `ItemRequestThread` (status `awaiting_warehouse` / `awaiting_branch` / `closed`; `last_activity_at`; `message_count`; close fields; M2M `items` traceability), `ThreadMessage` (append-only, explicit `side` branch|warehouse), `ThreadReadState` (read-cursor + unread badge), `ItemRequestThreadChangeLog` (lifecycle-only: created / item_linked / closed).
- **Gates:** branch via `active_branch_required` + other-branch **404**; warehouse via **capability** `is_warehouse_staff()` / `can_force_close_thread()` (the `threads` app deliberately has no Django group perms — `CATALOG_APP_LABELS` untouched).
- **Concurrency:** `post_message` and `close_thread` both `select_for_update`; post-to-closed raises `ThreadClosedError`; linking allowed after close.
- **Surfaces:** `/branch/threads/` (list + create + reply + close) and `/manage/threads/` (all branches incl. inactive-branch flagged, status/branch filters, oldest-awaiting-first, link-item search, admin force-close). Dashboard links added. i18n EN + pt-PT.
- **Seed:** one sample thread (North, awaiting warehouse) in `seed_dev_data`.
- **Tests:** `threads.tests` — state flips, opener-only close, override matrix (incl. deactivated opener), reason rules, other-branch 404, post-vs-close, capability gating, explicit side, unread → **459** total.
- **Manual:** [`08-request-threads.md`](user-manuals/08-request-threads.md).
- Plan: [`.cursor/plans/branch_request_threads_0d6a50a7.plan.md`](../.cursor/plans/branch_request_threads_0d6a50a7.plan.md) (complete; do not treat as a work queue).

### Warehouse FIFO stock reservation (D32) ✅

- **Locks:** R1–R12 accepted — reserve at **branch approve**; hold `min(remaining, unreserved on-hand)`; FIFO by `(approved_at, request.id, line.id)`; incoming stock auto-allocates; issue only from that line's hold; no `RESERVE` movement (D5); `available = on-hand − reserved`; branch hint uses available; approve never fails for lack of stock; negative adjust cannot go below reserved when reserved > 0.
- **Model:** `InternalRequestLine.quantity_reserved` (`Decimal(12,3)`, default 0); CheckConstraints `>= 0` and `<= quantity`; migration `orders/0002_line_quantity_reserved.py` with `backfill_reservations()`.
- **Services:** `inventory.services` allocate/release/reallocate helpers; wired from `approve` / `cancel`, `issue_goods`, `short_close_issue`, `receive_goods`, `adjust_stock`. Errors: `InsufficientReservationError`, `AdjustBelowReservedError`.
- **Surfaces:** manager catalog on-hand / reserved / available (below-reorder uses available); item drawer read-only on-hand/available; warehouse queue reserved/backorder/available; issue qty defaults to reserved; branch catalog hint from available.
- **Tests:** `inventory.tests.StockReservationTests` + `ConcurrentApproveTests` (+ catalog/branch hint cases) → **438** total.
- **Manuals:** [`01-items.md`](user-manuals/01-items.md), [`03-goods-receipts.md`](user-manuals/03-goods-receipts.md), [`04-internal-requests.md`](user-manuals/04-internal-requests.md), [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md), [`07-manager-catalog.md`](user-manuals/07-manager-catalog.md).
- Plan: [`.cursor/plans/stock_reservation_fifo_c7e19b04.plan.md`](../.cursor/plans/stock_reservation_fifo_c7e19b04.plan.md) (complete; do not treat as a work queue).

---

## Earlier today (23 Aug 2026) — already on main

### Sub-family stitch-in review ✅

- **Review (archived):** [`docs/archive/sub-family-review-2026-08-23-1345.md`](archive/sub-family-review-2026-08-23-1345.md) — no high-severity findings; four Low items fixed below.
- **Console JS:** `setLanguage()` refreshes sub-families drawer; `replaceItem()` keeps family/sub-family drawer item counts in sync after item create/update; `apiErrorMessage()` preserves quoted sub-family names in EN/pt-PT banners.
- **Tests:** +3 API cases (PATCH mismatch, clear `sub_family_id`, list payload includes `sub_families`) → **424** total.
- Review plan: [`.cursor/plans/sub-family_review_25223801.plan.md`](../.cursor/plans/sub-family_review_25223801.plan.md) (do not edit).

### Sub-families catalogue slice ✅

- **Model:** `SubFamily` + `SubFamilyChangeLog`; optional `Item.sub_family` FK; migration `0009_subfamily.py`.
- **Services:** family-mirroring CRUD, D16 activity (no cascade), mismatch checks; optional on create/update/Genesis.
- **Console:** item form field, toolbar filter, Sub-families drawer, APIs `/api/manage/sub-families/`; EN + pt-PT i18n.
- **Catalog surfaces:** manager catalog column + filter; branch catalog column (no filter).
- **Admin:** `SubFamilyAdmin`, changelog read-only, `ItemAdminForm` validation.
- **Seed / CLI:** sample sub-families in `seed_catalog_data.py`; `seed_dev_data` idempotent create; `add_item --sub-family`.
- **Tests:** service + API + catalog filter + branch payload (+19 tests → **421** at slice land; **424** after stitch-in review fixes).
- **Manuals:** [`01-items.md`](user-manuals/01-items.md) §7.1, [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md), [`07-manager-catalog.md`](user-manuals/07-manager-catalog.md).
- Plan: [`.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md`](../.cursor/plans/sub-family_catalogue_slice_afc2e074.plan.md) (do not edit the plan file).

---

## Earlier (22 Aug 2026, evening) — already on main

### Staff dashboard — missing page & API links ✅

- `/` now lists approval limits, internal requests, branch approval limits, branch pages (`/branch/select|catalog|requests|receipts/`), catalog/approval/internal-request/branch APIs, and PO reopen/cancel.

### Manage header — Settings gear + popover ✅

- Sticky header on `/manage/items/`, `/manage/catalog/`, `/manage/purchase-orders/`, `/manage/goods-receipts/`: left stays `CentCompras` + title; right is one gear button.
- Click opens an anchored **popover** (not a drawer): signed-in email, language, theme toggle, Sign out.
- Shared [`products/static/products/js/console_settings_menu.js`](../products/static/products/js/console_settings_menu.js); `data-i18n-aria` so i18n cannot wipe the SVG.
- `/` and `/branch/…` unchanged.
- Plan: [`.cursor/plans/manage_header_settings_popover_a1c3e7f2.plan.md`](../.cursor/plans/manage_header_settings_popover_a1c3e7f2.plan.md).
- Manuals: [`01-items.md`](user-manuals/01-items.md), [`02-purchase-orders.md`](user-manuals/02-purchase-orders.md), [`03-goods-receipts.md`](user-manuals/03-goods-receipts.md), [`07-manager-catalog.md`](user-manuals/07-manager-catalog.md).

---

## Earlier today (22 Aug 2026) — already on main

### Item `internal_code` — Phase 1 ✅

- Service: `InvalidInternalCodeError`; format `^[A-Za-z0-9._-]+$` (letters, digits, dots, hyphens, underscores).
- Console API returns `code: "invalid_internal_code"`; admin + i18n + HTML `pattern` on the item form.

### Item `internal_code` — Phase 2 ✅

- **`validate_item_genesis_ready`** + `ItemGenesisNotReadyError` — first activation requires internal code, description, unit, VAT, active family, **retail_price > 0**.
- **`InternalCodeImmutableError`** — code locked after first save; **set-if-empty once** for legacy rows.
- **`create_and_activate_item`** — atomic console POST (create + Genesis); no orphan inactive rows on cancel.
- Console UI: Genesis **pre-submit** confirmation; internal code required on new item, read-only on edit; i18n for new error codes.
- **`add_item` CLI**: `--internal-code` required; `--retail-price`; genesis validation on `--activate`.
- User manuals: [`01-items.md`](user-manuals/01-items.md), [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md).
- Plan complete: [`.cursor/plans/internal_code_format_rules_7862515a.plan.md`](../.cursor/plans/internal_code_format_rules_7862515a.plan.md).

### Requisição / receipt bug fixes ✅

| Bug | Fix |
|-----|-----|
| `str(ValidationError)` → quoted list in branch/warehouse order APIs | `orders/console_views.py`: `_validation_error_response()` uses `exc.messages[0]` |
| Branch receipts false “Goods issue not found” after full receive/short-close | `branch_receipts.html`: clear detail panel when dispatch drops off the open list |
| Warehouse short-close on `approved` with zero dispatch left request stuck in `shipped` | `short_close_issue`: `approved` → **closed**; `fulfilling` → **shipped**; added `approved → closed` transition |

Docs: [`04-internal-requests.md`](user-manuals/04-internal-requests.md) §7.2, [`05-edge-cases-and-limits.md`](user-manuals/05-edge-cases-and-limits.md) §4.2.

### Developer tooling ✅

- **Session handoff skill** — [`.cursor/skills/session-handoff/SKILL.md`](../.cursor/skills/session-handoff/SKILL.md)
- **Slash command** — `/session-handoff` ([`.cursor/commands/session-handoff.md`](../.cursor/commands/session-handoff.md))
- Agent rule: [`.cursor/rules/user-manuals.mdc`](../.cursor/rules/user-manuals.mdc) — update manuals when behaviour changes

---

## Live review (1303 — concluded & archived)

Archived: [`docs/archive/code-review-full-2026-08-21-1303.md`](archive/code-review-full-2026-08-21-1303.md). Do not treat as a work queue.

| ID | Sev | Summary | Status |
|----|-----|---------|--------|
| N1 | High | Approved PO with zero receipts cannot be cancelled | ✅ Done |
| N7 | Medium | Banker's rounding on `approved_*` totals | ✅ Done |
| N3 | Medium | PO pickers list inactive suppliers/items | ✅ Done |
| N5 | Medium | `reactivate_item` ignores inactive family | ✅ Done |
| N8 | Medium | Admin `InactiveFamilyError` → 500 | ✅ Done |
| N9 | Medium | Approve overflow on `approved_*` (14,2) | ✅ Done |
| N12 | Medium | `_parse_int_id` not used in products/inventory | ✅ Done |
| N4 | Low | `update_line` skips `full_clean` | ✅ Done |
| N10 | Low | Price `IntegrityError` always reported as duplicate | ✅ Done |
| N11 | Low | Receipt qty silent 3 dp quantize | ✅ Done |

All N1–N12 findings applied. (M7 and L13 were 2208 items, outside this review's scope — M7 is now done; L13 remains deferred.)

---

## Review progress (2208 — concluded)

Archived: [`docs/archive/code-review-full-2026-08-20-2208.md`](archive/code-review-full-2026-08-20-2208.md). Do not treat as a work queue.

| Batch | IDs | Status |
|-------|-----|--------|
| P0 | H1, H2, H3 | ✅ Done |
| P1 | M2, M3, M4, M9 | ✅ Done |
| P2 | M5, M6, M8 | ✅ Done; M7 done later (pagination) |
| P3 | M10 | ✅ Done (grades, approval limits, reasons, `on_commit` stub) |
| P4 | M1 + L1–L14 | ✅ Done (L13 deferred); review **archived** |
| — | M7 | ✅ Done (console pagination, 2026-08-21) |

Plans (reference only): `.cursor/plans/fix_h1_h2_h3_b4b6ce0c.plan.md`, `fix_p1_m2-m9_387eec3a.plan.md`, `fix_p2_m5_m6_m8_2372dbfd.plan.md`, `p4_m1_l1-l14_71ae16a5.plan.md`.

---

## Locked decisions (do NOT re-litigate)

| # | Decision |
|---|----------|
| D1 | Selling prices are **manual**; cost price is **dynamic** (from supplier list) |
| D2 | 3 selling prices: retail / wholesale / special (not branch-tiered) |
| D3 | Supplier price linked by **supplier + item** |
| D4 | `SupplierItemPrice` table, `unique(supplier, item)` |
| D5 | Stock = **movement ledger** + cached quantity on `Item` |
| D6 | **Many receipts per PO** (partial shipments) |
| D7 | PO status: `draft → submitted → approved/rejected → received → closed` |
| D8 | Rappel = simple per-line % for now |
| D9 | Email = stub (`notify_supplier_on_approval`), deferred to Phase 6 |
| D10 | Branches **built** (Phase 5 ✅) — `Item` stays global (no `branch_id`); `branches` + `orders` + branch receipt/stock live |
| D11 | `primary` = preferred supplier; auto-suggested later; always overridable |
| D12 | **B-hard:** a PO line is **rejected** if the PO's supplier has no price for the item (no fallback to another supplier's price) |
| D13 | **Approved totals snapshot:** `approved_net`/`approved_vat`/`approved_gross` stored once at `approve()` (frozen financial record; lines stay computed) |
| D14 | **One primary** `SupplierItemPrice` per item — DB partial unique `unique_primary_supplier_item_price`; lock Item; clear other primaries **before** save |
| D15 | **Duplicate PO lines rejected** (`unique_po_line_item`) — do **not** merge quantities |
| D16 | **Inactive entities:** no PO create/submit/approve/add-line for inactive supplier or item; catalog (`active_only=True`) excludes inactive families; cannot assign items to an inactive family. Do **not** cascade-deactivate items when a family is deactivated |
| D17 | Warehouse groups are **code-owned**: `sync_warehouse_groups()` still `permissions.set()` (extras in `/admin/` wiped on migrate). `assign_warehouse_group` is **exclusive** (one warehouse group per user) and **resets `warehouse_grade` to 1** |
| D18 | **Warehouse grades:** operator 1–2, manager 1–3, admin unlimited. Operator 1 view-only; operator 2 / manager 1 mutate the closed circuit; manager 2+ approve. Operators never approve. Caps in `ApprovalLimit` (EUR **gross**); admin-only edit at `/manage/approval-limits/`. Seed defaults: manager 2 self 100 / others 5_000; manager 3 self 500 / others 50_000 |
| D19 | **PO/stock reasons:** reject, manual close (remaining qty), and `adjust_stock` require a non-empty reason. Full receipt auto-close uses `"Fully received"`; `receive()` logs `"Goods received"`. Submit/approve/reopen reasons optional but wired. Email stub via `transaction.on_commit` (Phase 6 still pending) |
| D20 | Selling prices & `reorder_level` must be **finite and ≥ 0** (0 allowed). Enforced in services (`_validate_non_negative`), `MinValueValidator(0)`, and DB `CheckConstraint`s |
| D21 | **Family names are immutable** — create-only. `name` is not an updatable field; the family PATCH API does not rename |
| D22 | `SupplierItemPrice` can only be created for an **active** supplier **and** item |
| D23 | `VatRate.rate` is a fraction in `[0, 1]` (DB `CheckConstraint`) |
| D24 | PO line quantity upper bound = `1e9` (matches inventory) |
| D25 | `User.timezone` validated (IANA) in `clean()`; middleware `finally: deactivate()` so the timezone never leaks across requests |
| D26 | Dashboard shows permission codenames only for superusers / `DEBUG` |
| D27 | **Login rate limiting is a pre-production blocker** — deferred (`django-axes` or proxy); documented in `settings.example.py` |
| D28 | **Money rounding:** `ROUND_HALF_UP` (half away from zero). Unit costs → 4 dp first, then monetary amounts (net / vat / gross) → 2 dp. Implemented via `procurement.models.round_money`; the future `orders` app must reuse it |
| — | Dates DD/MM/YYYY (24h); per-user timezone (default `Europe/Lisbon`); EN + pt-PT |
| D29 | **`internal_code` lifecycle (Phases 1–2 ✅)** | Charset: `A–Z` `a–z` `0–9` `.` `-` `_`; max 64; unique case-insensitive. **Locked after first save** (set-if-empty once for legacy). Console create = **mandatory Genesis** (atomic); requires internal code + description + unit + VAT + active family + **retail_price > 0** |
| D30 | **Server-side item drafts** | **Deferred** — try localStorage autosave first if staff report lost forms; see plan advisory |
| D31 | **Warehouse short-close** | `approved` + zero dispatch → **closed**; `fulfilling` (partial issue) → **shipped** for branch receipt path |
| D32 | **Warehouse stock reservation** | At branch **approve**: hold `min(remaining, unreserved on-hand)` on `InternalRequestLine.quantity_reserved`. FIFO `(approved_at, request.id, line.id)`. Incoming stock auto-allocates. Issue only from that line's reserved qty. `available = on-hand − reserved`. Approve never fails for lack of stock. No `RESERVE` movement (D5). Negative `adjust_stock` cannot go below total reserved when reserved > 0. |

---

## What already landed (2208 — do not re-do)

**P0 — Highs**

- **H1** — `_lock_po()` before `add_line` / `update_line` / `remove_line` so line edits cannot race with submit/approve (D13 snapshot).
- **H2** — `accounts/authz.py`: `deny_if_inactive` / `user_is_active`. Django may treat an inactive session user as `AnonymousUser` while leaving `_auth_user_id`. Guards run **before** the auth check in all three `*_required` decorators; 403 `"Account is inactive"` + logout.
- **H3** — partial unique on primary supplier price; lock Item; clear other primaries before save. Migration `products/0006_unique_primary_supplier_item_price.py`.

**P1 — Mediums**

- **M3** — D12 price check on **submit and approve** (`_validate_all_lines_have_supplier_price`). Tests that delete a price must delete `SupplierItemPriceChangeLog` first (`PROTECT`).
- **M2** — `InactiveSupplierError` / `InactiveItemError` / `InactiveFamilyError`. Activity checks hit the DB (`filter(pk=..., is_active=True)`), not stale in-memory flags. `get_catalog(active_only=True)` also requires `family__is_active=True`.
- **M4** — `DuplicatePOLineError` + `unique_po_line_item` (`procurement/0004_unique_po_line_item.py`).
- **M9** — `_parse_int_id` (reject floats); add-line `DoesNotExist` → 404; `_write_movement` rejects balance ≥ 1e9.

**P2 — Mediums**

- **M5** — `CheckConstraint item_quantity_gte_zero` (`products/0007_item_quantity_gte_zero.py`); `inventory.services.ledger_quantity()`.
- **M6** — `receive_goods` locks items by sorted `pk` (`order_by("pk").select_for_update()`) before writing movements.
- **M8** — exclusive `assign_warehouse_group`; docstring on `sync_warehouse_groups`.

**P3 — M10**

- **Grades** — `User.warehouse_grade`; `accounts/capabilities.py` is the website source of truth (Django group perms are the coarse outer gate). Operators get add/change at group level; grade 1 is still view-only.
- **Approval limits** — `ApprovalLimit` / `ApprovalLimitChangeLog`; admin page `/manage/approval-limits/`. `approve()` enforces SoD + caps (admin unlimited).
- **Reasons** — required on `reject`, manual `close` (remaining qty), `adjust_stock`. Status changelog `reason` populated. Auto-close `"Fully received"`.
- **Email stub** — `transaction.on_commit(notify_supplier_on_approval)`; Phase 6 product not built.

**P4 — M1 + L1–L14 (review complete)**

- **M1** — `_validate_non_negative` for `reorder_level` + the three selling prices; `MinValueValidator(0)` + DB `CheckConstraint`s (`products/0008`).
- **L1** — non-empty `description` enforced in `create_item`/`update_item`.
- **L2** — family `name` removed from updatable fields + PATCH API.
- **L3** — `create_supplier_item_price` requires active supplier + item.
- **L4** — `VatRate.rate` in `[0, 1]`.
- **L5** — `line_vat` added to the line serializer.
- **L6** — console `_parse_decimal` now rejects NaN/Infinity (products + procurement).
- **L7** — PO `quantity` upper bound (1e9).
- **L8** — `User.clean()` timezone validation; middleware `finally: deactivate()`.
- **L9** — dashboard permission codenames hidden except superuser/DEBUG.
- **L10** — removed `StockMovement.Type.INITIAL` and `SupplierItemPriceChangeLog` DEACTIVATED/REACTIVATED (`inventory/0003`, `products/0008`).
- **L11** — removed unused `CHANGE_GOODS_RECEIPT`.
- **L12** — commented production-settings block in `settings.example.py`.
- **L13** — deferred (rate limiting) — documented blocker.
- **L14** — ledger-sum / concurrency / primary-race tests already present from H1/H3/M5.

**Seed bug (verified, fixed in `seed_dev_data`)**

`update_family()` returns a **new** `select_for_update` instance. The command stored the old object (`is_active=False`) after temporarily reactivating “Legacy stock”, so the follow-up pass skipped writing False and left the family **active**. A second seed then put LEG items in `get_catalog`.

Fix: `family = update_family(...)`; `refresh_from_db()` before the activity pass. Test: `test_second_seed_keeps_legacy_family_inactive`.

---

## Git (as of 24 August 2026, 11:20 WEST)

- **`main`** has Phase 5 Slices 1–6, internal_code Phases 1–2, Settings gear, sub-families, dashboard links, request threads, Company Voice, threads-review M/L, Company Voice review + H1/M/L/N2/N3, and this nits-parking note.
- Working tree may have local `.venv` noise — do **not** commit `.venv` deletions.

---

## Tests

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders threads company_voice --noinput
```

- Last full suite: **502 OK** with `--noinput` (includes warehouse FIFO reservation + request threads + Company Voice + review-fix tests).
- Fast hasher when `TESTING`. Quiet logging in tests.
- `--keepdb` can go stale after `TransactionTestCase` (missing `VatRate` / similar). Recreate **without** `--keepdb` if the suite blows up on missing tables/rows.

---

## Key files

```
products/       catalogue + pricing (models, services, console_views, admin, tests)
procurement/    purchase orders (models, services, console_views, admin, permissions, tests)
inventory/      goods receipt + stock ledger (models, services, console_views, admin, permissions, tests)
accounts/       custom User, warehouse groups, grades, login, timezone middleware, authz.py, capabilities.py
branches/       tenancy: Branch + BranchMembership, ActiveBranchMiddleware, picker, capabilities, admin, tests
orders/         internal request (requisição interna): models, services, console API, web UI, admin, tests
threads/        request threads (catalogue-gap requests): models, services, console API, web UI, admin, tests
company_voice/  Company Voice suggestion box: models, services, console API, web UI, admin, tests
config/         settings, urls
logging_utils/  rotating per-app logs
docs/           plan, handoff, archived reviews (incl. 1303), user-manuals/, tenancy design
```

**Conventions:** all mutations go through each app's `services.py`; audit-by-design (`*ChangeLog`); plain Django + vanilla JS; `select_for_update()` on updates.

---

## Run / test

```bash
source .venv/bin/activate
python manage.py migrate
./scripts/seed_dev_data.sh          # idempotent; VAT rates come from migration 0002
python manage.py runserver
.venv/bin/python manage.py test products accounts procurement inventory branches orders --noinput
```

- **Logins** (all `devpass123`): `warehouse.admin@centcompras.dev`, `warehouse.manager@…` / `manager2` / `manager3`, `warehouse.operator@…` / `operator2` (grades 1–3 as seeded). **Branch:** `branch.operator.north@…` / `branch.manager.north@…` / `branch.admin.north@…` (North), `branch.operator.south@…` / `branch.manager.south@…` (South), and `branch.dual@…` (both branches).
- **URLs:** `/` dashboard · `/manage/items/` item console · `/manage/catalog/` manager catalog · `/manage/purchase-orders/` PO console · `/manage/approval-limits/` PO caps (admin edit) · `/manage/goods-receipts/` goods receipt + stock · `/manage/internal-requests/` request queue + goods issue · `/manage/threads/` request threads (catalogue-gap) · `/manage/branch-approval-limits/` branch caps (admin edit) · `/company-voice/` Company Voice (all staff) · `/branch/select/` branch picker · `/branch/catalog/` branch catalog (cost hidden) · `/branch/requests/` requisição interna · `/branch/threads/` request threads (branch side) · `/admin/` superuser only.

---

## Docs map

| Doc | Purpose |
|-----|---------|
| `README.md` | setup, URLs, seed, how to run |
| `docs/PROJECT-PLAN.md` | **Living plan** — sequencing + status tracker + locked decisions; tick its tracker every session |
| `docs/archive/code-review-full-2026-08-21-1303.md` | Follow-up review — **concluded & archived** (N1–N12 applied) |
| `docs/reviews/threads-review-2026-08-24.md` | Request-threads review — **M1–M5 and L1–L6 applied**; leftover N1–N6 **recorded, not a queue** |
| `docs/reviews/company-voice-review-2026-08-24-1010.md` | Company Voice review — **H1, M1–M9, L1–L8, N2, N3 applied**; leftover N1 **recorded, not a queue** |
| `docs/archive/code-review-full-2026-08-20-2208.md` | Full review — **concluded & archived** (P0–P4 done; L13 deferred) |
| `docs/archive/code-review-full-2026-08-20-1928.md` | Prior full review — concluded |
| `docs/archive/code-review-audit.md` | historical catalogue hardening |
| `docs/archive/code-review-2026-08-20.md` | Phase 2 review — concluded |
| `docs/archive/code-review-inventory-2026-08-20.md` | Phase 3 review — concluded |
| `docs/user-manuals/` | staff user manuals (update when constraints change — see `.cursor/rules/user-manuals.mdc`) || `.cursor/plans/internal_code_format_rules_7862515a.plan.md` | Item `internal_code` — **complete** |
| `.cursor/plans/stock_reservation_fifo_c7e19b04.plan.md` | Warehouse FIFO reservation (D32 / R1–R12) — **complete** |
| `docs/archive/phase5-plan-260821-1756.md` | Phase 5 build spec (locks 1–10) — **archived** ✅ |
| `docs/archive/phase5-roadmap-260821-1618.md` | Phase 5 roadmap — **archived** ✅ |
| `docs/archive/phase5-brainstorm-260821-1530.md` | Phase 5 brainstorm + locked decisions (A1–B8) — **archived** ✅ |
| `docs/future-enhancements-260821-1833.md` | Future nice-to-haves (E items + later ideas) — parking lot, not Phase 5 |
| `docs/archive/warehouse-tenancy-setup.md` | **Archived** Branch/Membership sketch — superseded by brainstorm |
| `products/products_docs/aux_instructions.md` | learning pace for agents (not live status) |
| `.cursor/rules/` | agent rules — must match this handoff |
