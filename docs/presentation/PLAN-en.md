# CentCompras — Presentation plan (en)

**Version:** 1.0 · **Date:** 26 August 2026  
**URL:** `/presentation/en/` · **Language:** English — Portuguese at `/presentation/pt/`  
**Audience:** Central warehouse, branch managers and operators, leadership

---

## Objective

Communicate three core messages:

1. **Data is the new oil** — the sooner staff use CentCompras daily, the sooner the company has reliable information for charts and decisions.
2. **Closed circuit** — from item to stock, through procurement, authorization, and shipment.
3. **Circularity** — when an item does not exist, the cycle starts elsewhere (request threads) and closes with human feedback (thread satisfaction + Company Voice).

The presentation is **informational** (no live data). Charts marked **future vision** are illustrative.

---

## Narrative (4 acts)

| Act | Slides | Message |
|-----|--------|---------|
| **I — Why** | 1–4 | Context, data metaphor, what is already recorded today |
| **II — Closed circuit** | 5–11 | Warehouse flow: catalogue → procurement → approval → stock → branch |
| **III — Circularity** | 12–14 | Missing item → thread → catalogue → request → feedback |
| **IV — Call to action** | 15–16 | Roles, next steps, start now |

---

## Slide map

### Slide 1 — Title
- **Title:** CentCompras — Centralised logistics with branches
- **Subtitle:** Data, circuits, and circularity
- **Notes:** Present the system as a single platform (PostgreSQL = source of truth).

### Slide 2 — Scenario
- Central warehouse + satellite branches
- Today: catalogue, purchase orders, receipts, requests, threads, Company Voice, offline PWA at branches
- **Notes:** Not a prototype — phases 0–6 complete (548 tests).

### Slide 3 — Data is the new oil
- Metaphor: crude vs refined oil; raw data vs decisions
- Every click generates structured events (stock movements, PO states, approvals, audit)
- **Notes:** Emphasize you do not need to wait for charts to start using the system.

### Slide 4 — What the system already records
- Table: `StockMovement`, `ItemChangeLog`, PO states, `InternalRequest`, `ThreadMessage`, `VoicePost`
- **Notes:** Link to real models in code; zero direct quantity typing.

### Slide 5 — Future vision: charts *(mock)*
- Illustrative charts: stock over time, POs by state, requests per branch
- Visible label: **FUTURE VISION — real data accumulates with use**
- **Notes:** Honest about what exists vs what is coming.

### Slide 6 — Two worlds, one system
- Warehouse (`/manage/…`) vs branch (`/branch/…`)
- Roles: admin/manager/operator (warehouse and branch)
- **Notes:** Warehouse groups ≠ branch roles.

### Slide 7 — Closed circuit (diagram)
- SVG: Catalogue → Procurement → Approval → Central stock → Request → Issue → Branch receipt
- **Notes:** Bird's-eye view before detailing each step.

### Slide 8 — Catalogue and pricing
- `/manage/items/` — families, items, `internal_code`, selling and supplier prices
- Genesis: activation with retail price > 0
- **Notes:** Item inactive until qualified.

### Slide 9 — Procurement
- `/manage/purchase-orders/` — draft → submitted → approved → received
- Line rejected if supplier has no price for item
- **Notes:** Links to `SupplierItemPrice`.

### Slide 10 — Authorization
- Grade + EUR gross limits (`/manage/approval-limits/`)
- Branch: caps at `/manage/branch-approval-limits/`
- **Notes:** Operators never approve POs.

### Slide 11 — Central stock
- `/manage/goods-receipts/` → `StockMovement` ledger
- FIFO reservation (D32): available = on-hand − reserved
- **Notes:** `Item.quantity` only via movements.

### Slide 12 — Internal request
- Branch: draft → approval → warehouse issues (`/manage/internal-requests/`)
- Offline: drafts in local queue (PWA)
- **Notes:** Approve never fails for lack of stock; reserves what is on hand.

### Slide 13 — Branch receipt
- `/branch/receipts/` — branch stock increases
- `BranchStockMovement` ledger
- **Notes:** Closes the branch circuit.

### Slide 14 — Circularity (diagram)
- Item missing → `/branch/threads/` → dialogue → create item → link → normal request → close thread (satisfaction)
- **Notes:** Thread ≠ order; item created in normal catalogue flow.

### Slide 15 — Continuous feedback
- Company Voice (`/company-voice/`) — praise, concerns, suggestions
- Threads: satisfaction rating on close
- **Notes:** Closes the human loop.

### Slide 16 — Next steps
- Start now: every transaction feeds future analytics
- Role-based training; manuals at `docs/user-manuals/en/`
- Phase 7: production deployment readiness
- **Notes:** Concrete call to action.

---

## Technical resources

| Component | Location |
|-----------|----------|
| Plan (this file) | `docs/presentation/PLAN-en.md` |
| Portuguese plan | `docs/presentation/PLAN-pt-PT.md` |
| Django app | `presentation/` |
| PT template | `presentation/templates/presentation/deck_pt.html` |
| EN template | `presentation/templates/presentation/deck_en.html` |
| Shared CSS / JS | `presentation/static/presentation/` |
| Routes | `/presentation/` and `/presentation/pt/` → PT · `/presentation/en/` → EN |

### Deck navigation
- Arrow keys ← →, Space, Page Up/Down
- Progress bar; slide counter
- `F` fullscreen; `?` help
- Language switcher in footer
- Responsive (projector + tablet)

---

## Code references

| Concept | App / file |
|---------|------------|
| Catalogue | `products/services.py`, `/manage/items/` |
| Purchase orders | `procurement/`, `/manage/purchase-orders/` |
| Stock | `inventory/services.py`, `StockMovement` |
| Internal request | `orders/`, `/branch/requests/` |
| Threads | `threads/`, `/branch/threads/` |
| Company Voice | `company_voice/`, `/company-voice/` |
| Branches | `branches/`, `ActiveBranchMiddleware` |
| EN manuals | `docs/user-manuals/en/` |
