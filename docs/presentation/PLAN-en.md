# CentCompras — Presentation plan (en)

**Version:** 2.7 · **Date:** 11 September 2026  
**URL:** `/presentation/en/` · **Language:** English — Portuguese at `/presentation/pt/`  
**Audience:** Central warehouse, branch managers and operators, leadership

---

## Objective

Communicate four core messages:

1. **Start today** — role-based call to action; data compounds with daily use (slide 11).
2. **Data is the new oil** — the sooner staff use CentCompras daily, the sooner the company has reliable information for charts and decisions (slide 13).
3. **Closed circuit** — from item to stock, through procurement, authorization, and shipment.
4. **Two human channels** — request threads are **bounded conversations that close** (slide 9); Company Voice is an **ongoing feed** that never closes (slide 12).

The presentation is **informational** (no live data). Charts marked **future vision** are illustrative. An image is worth a thousand words: slides 2–9 lead with SVG; URL paths and code names stay off those slides.

---

## Narrative

| Act | Slides | Message |
|-----|--------|---------|
| **I — Hook + orientation** | 1–3 | Title, bird's-eye map, closed circuit (CEM-50) |
| **II — Operations (graphics)** | 4–8 | Request, branch receipt, catalogue, procurement, central stock |
| **III — Gap + vision** | 9–10 | Missing-item conversation, future charts |
| **IV — Call to action + remaining channel** | 11–12 | Role-based CTA, Company Voice |
| **V — Why + what is recorded** | 13–15 | Data metaphor, scenario, ledger table |
| **VI — Controls + demo** | 16–17 | Authorization, demo login |

---

## Slide map

### Slide 1 — Title
- **Title:** CentCompras — Centralised logistics with branches
- **Subtitle:** Data, circuits, and circularity
- **Notes:** Present the system as a single platform (PostgreSQL = source of truth).

### Slide 2 — One system, two workplaces
- Eyebrow: **The big picture**; title: **One system, two workplaces**
- Subtitle: central warehouse + a branch **(branches)** — same application, two workplaces
- Bird's-eye SVG: large warehouse circle (top) + smaller branch circle (lower left)
- Amber arrow + label **We need this** (branch → warehouse); teal return arch + label **Here it is** (warehouse → branch)
- Unit bullets under diagram; **Branch** heading mustard (`#f59e0b`); warehouse heading teal
- Footer: **The branch asks. The warehouse answers.**

### Slide 3 — Closed circuit (diagram)
- Title **From item to branch stock**; footer unchanged (circuit closes when the branch confirms)
- Subline: *Example: CEM-50 — Cement 50 kg. Already in the catalogue; the circuit closes at the branch.*
- Racetrack SVG (warehouse upper-right / branch lower-left): **Asks** (CEM-50 chip) → **Stock**; dashed **No stock** detour **Order → Receipt** (caption *order becomes a receipt*) back to Stock → **Shipped** → **Confirm** (latch)
- No URL paths; no Approval node; no Catálogo box; coloured arrows stop at Confirm

### Slide 4 — Internal request
- Subline: *The branch asks; the warehouse ships.*
- Two columns (not boxed): **Branch** mustard — Catalogue → Draft → Submit; **Warehouse** teal — Queue → Ship → **status → shipped** (double vertical bar between Ship and status, no arrow); mustard **Approved** handoff
- Two short bullets per column; no URL paths

### Slide 5 — Branch receipt
- SVG: **Shipped** → **Confirm qty** → **Branch stock up**; gray **Partial / close** and **Admin adjust**
- Keep closed-circuit footer; no bullets; no URL paths

### Slide 6 — Catalogue and pricing
- Subline: *Only the warehouse manages the catalogue.*
- Constellation: **Item** centre; Family, Supplier, Prices, Genesis → Active
- Two short lines + inactive-until-ready footer; no URL paths; no model names

### Slide 7 — Procurement
- Subline: *From draft to closed.*
- Zigzag: Draft → Validated → Submitted → Approved → Received / Closed
- Footer only (no supplier price = no line); no bullet list

### Slide 8 — Central stock
- Subline: *Quantity is never typed by hand.*
- On-hand mass with mustard **Reserved** bite; **Available = on hand − reserved**
- Two short lines; no ledger jargon / D32

### Slide 9 — When the item does not exist
- **Title:** When the item is not in the catalogue
- **Subline:** *Not an order — a conversation that closes once the item enters the catalogue.*
- Open 5-step SVG: **Can't find it** → **New conversation** (outer box with **Branch** ↔ **Warehouse** inside) → **Understanding reached** → **Inserted in catalogue** → **Conversation closes**
- Mustard arrow only from Can't find it to New conversation; to-and-fro arrows are inside the conversation box; gray spine below stops at box borders

### Slide 10 — Future vision: charts *(mock)*
- Illustrative charts; label **Future vision — illustrative**

### Slide 11 — What we need from you (CTA)
- Four role-based actions: warehouse, branches, management, everyone

### Slide 12 — Company Voice (finale)
- Text + ongoing feed panel; still **Company Voice** in the deck (Parle rename D40 not applied here)

### Slide 13 — Data is the new oil
- Metaphor: crude vs refined oil; raw data vs decisions

### Slide 14 — Today's scenario
- Central warehouse + satellite branches; module list

### Slide 15 — What the system already records
- Table of models; golden rule — stock only via ledger movements

### Slide 16 — Authorization
- PO limits + branch request caps
- Headings: **Warehouse** teal (`#14b8a6`); **Branch** mustard (`#f59e0b`)

### Slide 17 — Try the app (demo login)
- HTTP demo alert; `DEMO_LOGIN_URL`; password `devpass123`; warehouse + branch tables
- **Central warehouse** heading teal; **Branches** heading and **Branch** column mustard

---

## Technical resources

| Component | Location |
|-----------|----------|
| Plan (this file) | `docs/presentation/PLAN-en.md` |
| Portuguese plan | `docs/presentation/PLAN-pt-PT.md` |
| Django app | `presentation/` |
| PT template | `presentation/templates/presentation/deck_pt.html` |
| EN template | `presentation/templates/presentation/deck_en.html` |
| Shared CSS / JS | `presentation/static/presentation/` (`deck.css?v=23` on working tree — includes TEMP `.viewbox-debug`; remove before presenting), `deck.js` |
| Routes | `/presentation/` and `/presentation/pt/` → PT · `/presentation/en/` → EN |

### Deck navigation
- Arrow keys ← →, Space, Page Up/Down
- Progress bar; slide counter
- `F` fullscreen; `?` help
- Language switcher in footer
- Responsive (projector + tablet)

### SVG canvas (slides 3–9 process graphics)
Slides **3–5, 7–8, and 9** use a **710-wide** `viewBox` (same as slide 6) so labels and strokes render at the same on-screen weight when scaled to `max-width: 640px`. Drawings stay in their original coordinates inside `<g transform="translate(75, 0)">` (slide 9: `translate(85, 0)`). Slide 2 keeps its own `520` bird's-eye canvas.

### Visual-layout sub-agent
For slide graphics, launch a **generalPurpose** design consultant first (slides 4–9 used [Visual layout](0748cef2-9c52-4b6f-b63b-0403d19e6e3f) / [Visual layout](31643dbd-721a-469e-b694-8836bf6626d9)). Tokens: warehouse teal `#14b8a6`, branch mustard `#f59e0b`, gray `#94a3b8`; rounded nodes; no boxed columns; no URL paths; everyday words.

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
