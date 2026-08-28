# CentCompras — Presentation plan (en)

**Version:** 2.0 · **Date:** 28 August 2026  
**URL:** `/presentation/en/` · **Language:** English — Portuguese at `/presentation/pt/`  
**Audience:** Central warehouse, branch managers and operators, leadership

---

## Objective

Communicate four core messages:

1. **Start today** — role-based call to action up front; data compounds with daily use.
2. **Data is the new oil** — the sooner staff use CentCompras daily, the sooner the company has reliable information for charts and decisions.
3. **Closed circuit** — from item to stock, through procurement, authorization, and shipment.
4. **Two human channels** — request threads are **bounded conversations that close**; Company Voice is an **ongoing feed** that never closes.

The presentation is **informational** (no live data). Charts marked **future vision** are illustrative.

---

## Narrative (5 acts)

| Act | Slides | Message |
|-----|--------|---------|
| **I — Hook** | 1–2 | Title + call to action (what we need from you) |
| **II — Why** | 3–6 | Scenario, data metaphor, what is recorded, future vision |
| **III — Closed circuit** | 7–14 | Architecture + warehouse flow through branch receipt |
| **IV — Circularity** | 15 | Catalogue-gap thread circuit (closes) |
| **V — Send-off** | 16 | Company Voice finale (text + ongoing feed panel) |

---

## Slide map

### Slide 1 — Title
- **Title:** CentCompras — Centralised logistics with branches
- **Subtitle:** Data, circuits, and circularity
- **Notes:** Present the system as a single platform (PostgreSQL = source of truth).

### Slide 2 — What we need from you (CTA)
- Eyebrow: **What we need from you**
- Four role-based actions: warehouse, branches, management, everyone
- **Notes:** No manuals/Phase 7 footer here — urgency first; foreshadows Company Voice (item 4).

### Slide 3 — Today's scenario
- Central warehouse + satellite branches; single-column list of modules (no card grid)
- **Notes:** Not a prototype — phases 0–6 complete (548 tests).

### Slide 4 — Data is the new oil
- Metaphor: crude vs refined oil; raw data vs decisions
- **Notes:** Emphasize you do not need to wait for charts to start using the system.

### Slide 5 — What the system already records
- Table: `StockMovement`, `ItemChangeLog`, PO states, `InternalRequest`, `ThreadMessage`, `VoicePost`
- **Notes:** Golden rule — stock only via ledger movements.

### Slide 6 — Future vision: charts *(mock)*
- Illustrative charts; label **Future vision — illustrative**
- **Notes:** Honest about what exists vs what is coming.

### Slide 7 — Two worlds, one system
- Warehouse (`/manage/…`) vs branch (`/branch/…`)
- **Notes:** Warehouse groups ≠ branch roles.

### Slide 8 — Closed circuit (diagram)
- SVG: Catalogue → Procurement → Approval → Stock → Request → Issue → Branch receipt
- **Notes:** Bird's-eye view before step slides.

### Slide 9 — Catalogue and pricing
- `/manage/items/` — families, Genesis, audit
- **Notes:** Item inactive until qualified.

### Slide 10 — Procurement
- `/manage/purchase-orders/` — draft through received/closed
- **Notes:** No supplier price → no line.

### Slide 11 — Authorization
- PO limits + branch request caps
- **Notes:** Operators never approve POs.

### Slide 12 — Central stock
- `/manage/goods-receipts/` → `StockMovement`; FIFO reservation (D32)
- **Notes:** `Item.quantity` only via movements.

### Slide 13 — Internal request
- Branch draft/offline + warehouse issue
- **Notes:** Approve never fails for lack of stock.

### Slide 14 — Branch receipt
- `/branch/receipts/` — closes the operational circuit
- **Notes:** Every step recorded.

### Slide 15 — Circularity (thread circuit only)
- Full-width thread circuit diagram (catalogue gap → open → dialogue → create → link → normal request → close)
- Loop label: next catalogue gap → new thread
- Thread bullets + caption below (two columns)
- **Notes:** No Company Voice on this slide — circularity is only for missing items.

### Slide 16 — Company Voice (finale)
- Text copy (left) + ongoing feed panel illustration (right)
- Eyebrow: **Keep talking**; emotional send-off
- Footer: manuals · Phase 7
- **Notes:** Feed visual moved here from slide 15; stream never closes.

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
