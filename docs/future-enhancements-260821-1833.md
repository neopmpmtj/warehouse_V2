# CentCompras — Future enhancements (nice-to-have)

> **Created:** 21 August 2026, 18:33 WEST.  
> **Status:** parking lot — not scheduled, not Phase 5 scope. Promote an item into a phase plan before building it.  
> Source: Phase 5 plan review pass (set E) plus later ideas that surfaced in the same review.

## E — from the Phase 5 plan review

| # | Idea | Why deferred / notes |
|---|------|---------------------|
| E1 | **Branch-level "low stock" hint** | After Slice 5 the branch ledger exists; a read-only flag helps branches re-request before running dry. Not required for Phase 5 done. |
| E2 | **Minimal "switch to branch view" affordance** | For the rare dual-role (warehouse + branch) user; a link, not a restyle of `/` (respects lock 5). |
| E3 | **Manager batch-approve** | Approve several small submitted requests in one action (caps still applied per request); guard with "select all below your self cap". |

## Other known later items (already tracked in PROJECT-PLAN / roadmap)

Kept here as a single glanceable list; the authoritative sequencing stays in `PROJECT-PLAN.md` §7 / §16–18.

- Offline / PWA / Service Worker / idempotent sync — Phase 6
- Email automation (real send) — Phase 8
- Google OAuth / public signup / password reset — production (later)
- Linked / auto PO (full automation) — beyond Phase 5's manual shortfall path (C1/C2 are the Phase 5 seam)
- Branch-tiered prices — D2 unchanged
- Shared chrome / restyle `/` — deferred
- Per-branch approval caps — lock 2 (global table only for MVP)
