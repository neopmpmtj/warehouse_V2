# CentCompras — Presentation plan (en)

**Version:** 2.2 · **Date:** 29 August 2026  
**URL:** `/presentation/en/` · **Language:** English — Portuguese at `/presentation/pt/`  
**Audience:** Central warehouse, branch managers and operators, leadership

---

## Objective

Communicate four core messages:

1. **Start today** — role-based call to action; data compounds with daily use (slide 14, before send-off).
2. **Data is the new oil** — the sooner staff use CentCompras daily, the sooner the company has reliable information for charts and decisions.
3. **Closed circuit** — from item to stock, through procurement, authorization, and shipment.
4. **Two human channels** — request threads are **bounded conversations that close**; Company Voice is an **ongoing feed** that never closes.

The presentation is **informational** (no live data). Charts marked **future vision** are illustrative.

---

## Narrative (6 acts)

| Act | Slides | Message |
|-----|--------|---------|
| **I — Hook + why** | 1–4 | Title, data metaphor, scenario, what is recorded |
| **II — Branch flow first** | 5–6 | Internal request + branch receipt |
| **III — Warehouse steps** | 7–10 | Catalogue through central stock |
| **IV — Architecture + vision** | 11–13 | Closed circuit diagram, two worlds, future charts |
| **V — Call to action** | 14 | Role-based CTA (moved late) |
| **VI — Human channels + hands-on** | 15–17 | Threads, Company Voice, demo login |

---

## Slide map

### Slide 1 — Title
- **Title:** CentCompras — Centralised logistics with branches
- **Subtitle:** Data, circuits, and circularity
- **Notes:** Present the system as a single platform (PostgreSQL = source of truth).

### Slide 2 — Data is the new oil
- Metaphor: crude vs refined oil; raw data vs decisions
- **Notes:** Emphasize you do not need to wait for charts to start using the system.

### Slide 3 — Today's scenario
- Central warehouse + satellite branches; single-column list of modules (no card grid)
- **Notes:** Not a prototype — phases 0–6 complete.

### Slide 4 — What the system already records
- Table: `StockMovement`, `ItemChangeLog`, PO states, `InternalRequest`, `ThreadMessage`, `VoicePost`
- **Notes:** Golden rule — stock only via ledger movements.

### Slide 5 — Internal request
- Branch draft/offline + warehouse issue
- **Notes:** Approve never fails for lack of stock.

### Slide 6 — Branch receipt
- `/branch/receipts/` — closes the operational circuit from the branch side
- **Notes:** Every step recorded.

### Slide 7 — Catalogue and pricing
- `/manage/items/` — families, Genesis, audit
- **Notes:** Item inactive until qualified.

### Slide 8 — Procurement
- `/manage/purchase-orders/` — draft through received/closed
- **Notes:** No supplier price → no line.

### Slide 9 — Authorization
- PO limits + branch request caps
- **Notes:** Operators never approve POs.

### Slide 10 — Central stock
- `/manage/goods-receipts/` → `StockMovement`; FIFO reservation (D32)
- **Notes:** `Item.quantity` only via movements.

### Slide 11 — Closed circuit (diagram)
- SVG: Catalogue → Procurement → Approval → Stock → Request → Issue → Branch receipt
- **Notes:** Bird's-eye view after operational step slides.

### Slide 12 — Two worlds, one system
- Warehouse (`/manage/…`) vs branch (`/branch/…`)
- **Notes:** Warehouse groups ≠ branch roles.

### Slide 13 — Future vision: charts *(mock)*
- Illustrative charts; label **Future vision — illustrative**
- **Notes:** Honest about what exists vs what is coming.

### Slide 14 — What we need from you (CTA)
- Eyebrow: **What we need from you**
- Four role-based actions: warehouse, branches, management, everyone
- **Notes:** No manuals/Phase 7 footer here — urgency before send-off; foreshadows Company Voice (item 4).

### Slide 15 — Circularity (thread circuit only)
- Full-width thread circuit diagram (catalogue gap → open → dialogue → create → link → normal request → close)
- Loop label: next catalogue gap → new thread
- Thread bullets + caption below (two columns)
- **Notes:** No Company Voice on this slide — circularity is only for missing items.

### Slide 16 — Company Voice (finale)
- Text copy (left) + ongoing feed panel illustration (right)
- Eyebrow: **Keep talking**; emotional send-off
- Footer: manuals · Phase 7
- **Notes:** Stream never closes.

### Slide 17 — Try the app (demo login)
- Eyebrow: **Try it now**
- HTTP demo alert (browser “Not secure” warning expected)
- Login URL: from `presentation/views.py` (`DEMO_LOGIN_URL`)
- Password: `devpass123` (all seeded users)
- Two tables: warehouse (6) + branches (6 incl. dual)
- **Notes:** Last slide — audience logs in immediately after the deck.

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
