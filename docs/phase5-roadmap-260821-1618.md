# Phase 5 — Full roadmap (step by step)

> **For tired-you and the next developer.** Created 21 Aug 2026, 16:18 WEST.  
> **Decisions are locked** — do not re-open A1–B8 unless the business changes. See [`phase5-brainstorm-260821-1530.md`](phase5-brainstorm-260821-1530.md) §Locked decisions.  
> **Rule:** one slice per session; green tests before the next slice.

---

## Where you are now (nothing to decide)

| Done | Not done |
|------|----------|
| Phases 0–4 (warehouse loop) | `branches/`, branch requests, goods issue, branch stock |
| Brainstorm + all ambiguities locked | Formal build plan doc |
| Living docs synced to locked decisions | Phase 5 code |

**You do not need to re-read every review or tenancy doc.** Read this file + brainstorm locked § + `handoff.md`.

---

## Step 0 — Doc sync ✅ (this session)

Living docs updated so nothing contradicts locked Phase 5 decisions:

- [`handoff.md`](handoff.md) — Phase 5 = planning; links below
- [`PROJECT-PLAN.md`](PROJECT-PLAN.md) — §12 fixed (offline → Phase 7)
- [`archive/warehouse-tenancy-setup.md`](archive/warehouse-tenancy-setup.md) — archived; superseded by brainstorm locked §
- [`README.md`](../README.md) + [`AGENTS.md`](../AGENTS.md) — pointers + branch role names
- [`user-manuals/02-purchase-orders.md`](user-manuals/02-purchase-orders.md) — approve = manager g2+ (matches code)

**Skip:** archived reviews, `.cursor/plans/*`, `products/README.md` (history only).

---

## Step 1 — Formal plan doc (next work session, ~1–2 h, no code)

**Create:** `docs/phase5-plan-260821-HHMM.md`

**Copy from brainstorm, reorganise into build spec:**

1. **Goal** — one paragraph (branch requisição → warehouse issue → branch receipt).
2. **Apps** — `branches`, `orders` (internal requests), extend `inventory` (GoodsIssue + branch stock app or sub-module — pick one name in plan).
3. **Models** — ERD bullet list (fields, FKs, constraints, nullable PO link on lines).
4. **Status machines** — internal request + line fulfilment states; goods issue; branch receipt.
5. **Permissions** — `operator` / `manager` / `admin` capability table.
6. **Services** — function list per app (mirror PO/GR naming).
7. **URLs** — branch + warehouse consoles + APIs.
8. **Slices** — Steps 2–7 below as checklist with Definition of Done each.
9. **Tests** — isolation, caps, over-issue, over-receipt, inactive item.
10. **Out of scope** — offline (Phase 7), email (Phase 6), linked/auto PO (later slice), reservation (deferred).

**Then update:** `handoff.md` “Next task” → Slice 1; `PROJECT-PLAN.md` status tracker tick “plan authored”.

**Stop.** Do not code until plan exists.

---

## Step 2 — Slice 1: Tenancy foundation (first code session)

**Build**

- `branches` app: `Branch`, `BranchMembership` (`operator` | `manager` | `admin`)
- `branches/permissions.py`, `branches/capabilities.py` (mirror `accounts/capabilities.py`)
- `ActiveBranchMiddleware` + `/branch/select/` picker
- Django admin for Branch + Membership
- Seed: 2 branches, operator + manager per branch, one dual-membership user

**Do not build:** requests, catalog UI, goods issue.

**Done when**

- Tests: tenant isolation, picker, 0/1/N memberships
- `migrate` clean; full suite still green

---

## Step 3 — Slice 2: Branch catalog (read-only)

**Build**

- `/branch/catalog/` + `GET /api/branch/catalog/`
- Reuse `get_catalog(active_only=True)`; **hide cost**; show **availability hint** (in stock / low / none)
- Gate: branch membership on active branch only

**Done when**

- Branch user sees catalog; warehouse user without membership gets 403/redirect
- Tests for cost not in API payload

---

## Step 4 — Slice 3: Internal request (branch side only)

**Build**

- `orders` app (name locked in plan): header + lines, snapshots, change logs
- Services: create, add/update/remove line, submit, approve, reject, cancel (per B8)
- Priced: snapshot wholesale + VAT at **approve**; `approved_*` on header; manager caps (mirror `ApprovalLimit` — new table or branch-scoped)
- Branch UI: `/branch/requests/` — draft through approved
- Line fulfilment state + **nullable PO FK** on schema (unused)

**Do not build:** warehouse queue, goods issue, branch receipt.

**Done when**

- Operator can draft/submit; manager approve/reject; operator cannot approve
- Warehouse cannot see `submitted` — only `approved+` (B5)
- Tests: workflow, caps, duplicate line, inactive item blocked

---

## Step 5 — Slice 4: Warehouse goods issue

**Build**

- `GoodsIssue` + `GoodsIssueLine` in `inventory`
- `issue_goods(request, lines, user)` → negative `GOODS_ISSUE` movements
- Warehouse console: `/manage/internal-requests/` — queue of **approved** requests
- Partial issue OK; short-close with reason (A8)
- No reservation — check stock at issue (A4)

**Done when**

- Issue decrements `Item.quantity`; cannot issue > on-hand or > request remaining
- Tests: partial issue, concurrent issue, negative stock guard

---

## Step 6 — Slice 5: Branch goods receipt + branch stock

**Build**

- Branch stock: `BranchStockMovement` + cached qty per `(branch, item)`
- `BranchReceipt` + lines linked to goods issue / request lines
- `receive_at_branch()` — reject over-receipt vs shipped (A9)
- Branch UI: `/branch/receipts/`
- Branch admin: `adjust_branch_stock()` with reason

**Done when**

- Full loop: request → issue → branch receipt → branch stock updated
- Request closes when fully received or short-closed
- Tests: over-receipt rejected, partial receipt

---

## Step 7 — Slice 6: Polish + docs (before calling Phase 5 done)

- Seed script: branch users + sample request
- User manual stub or section in new `04-internal-requests.md`
- Update `handoff.md`, `PROJECT-PLAN.md` tracker — Phase 5 ✅
- Full test suite green

**Explicitly later (do not block Phase 5 done)**

- Linked PO / auto-draft PO (A5 seams already in schema)
- Stock reservation (A4)
- Branch UI showing money totals (A3 — model already priced)
- Notifications (B7 / Phase 6)
- Offline (B1 / Phase 7)

---

## Session cheat sheet (when overwhelmed)

| If you have… | Do this only |
|--------------|--------------|
| 30 min | Read this roadmap + brainstorm locked § |
| 1–2 h | Write `phase5-plan-*.md` (Step 1) |
| Half day | One slice (Steps 2–6); run tests |
| Tired | Stop after tests green; update handoff one line |

---

## Test command (every session)

```bash
.venv/bin/python manage.py test products accounts procurement inventory branches orders --keepdb --noinput
```

(Add `branches` / `orders` app names as they appear.)

---

## What never to do in Phase 5

- Implement tenancy-doc §6–7 `item_name` stub
- Offline queue / Service Worker
- Real email
- Shared chrome / restyle `/`
- Auto PO without human PO approve
- `branch_id` on `Item`

---

## Doc map (after sync)

| Read order | File |
|------------|------|
| 1 | [`handoff.md`](handoff.md) |
| 2 | This roadmap |
| 3 | [`phase5-brainstorm-260821-1530.md`](phase5-brainstorm-260821-1530.md) locked § |
| 4 | `phase5-plan-*.md` (when written) |
| 5 | [`PROJECT-PLAN.md`](PROJECT-PLAN.md) §12 |

[`docs/archive/warehouse-tenancy-setup.md`](archive/warehouse-tenancy-setup.md) — archived sketch only.

---

## Appendix — Step 1 done + build-spec locks 1–10 (21 Aug 2026, 17:56 WEST)

**Do not edit the sections above.** This appendix records the formal plan and the session locks that the plan encodes.

**Plan (build spec):** [`phase5-plan-260821-1756.md`](phase5-plan-260821-1756.md)

**Next work session:** Slice 1 (Step 2) — `branches` app only. Do not start requests or stock.

| # | Lock |
|---|------|
| 1 | Apps: `branches` + `orders` + extend `inventory` (goods issue **and** branch stock). No `branch_inventory` app. |
| 2 | One global manager cap table (self vs others), warehouse admin edits. Per-branch later. |
| 3 | Keep the long **header** status list (`draft` → `submitted` → `approved`/`rejected` → `fulfilling` → `shipped` → `received` → `closed` + `cancelled`). No status on lines. Nullable PO FK on lines for later automation. |
| 4 | `BranchReceipt` hangs off `GoodsIssue` (the dispatch/guia). |
| 5 | Post-login: warehouse (including dual) → `/`. Branch-only → `/branch/catalog/` or `/branch/select/`. Do not restyle `/`. |
| 6 | `wholesale_price == 0` → reject the line (add, submit, approve). |
| 7 | Stock hint: none / low / in stock. Low = at or below reorder level. No exact warehouse qty. |
| 8 | Short-close on both sides, never operators, reason required. Warehouse writes off **unshipped** remainder; branch writes off **unreceived** remainder. |
| 9 | Inactive branch: no new requests/lines/submit/approve. In-flight issue/receipt/close still allowed. |
| 10 | Head office creates branch users and memberships in `/admin/` (superuser). Branch staff do not create logins. **Manager** = requisição. **Admin** = that plus overrides and branch stock correct — still no hire-colleagues screen in Phase 5. |

Policy A1–B8 remains in the brainstorm locked §. If this appendix and an older brainstorm section disagree, **this appendix + the plan** win.
