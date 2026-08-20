# Auxiliary Instructions for a Coding Agent — CentCompras MVP

## Purpose

You are taking over or reproducing a small Django warehouse catalogue MVP named **CentCompras**.

The human developer is entry/mid-level and is intentionally learning the architecture while building it.

Do **not** respond by replacing the project with a large, sophisticated, fully finished system.

Preserve the incremental architecture and explain changes in understandable phases.

**Live project state is not in this file.** Read [`docs/handoff.md`](../../docs/handoff.md) first. Setup: [`README.md`](../../README.md).

---

# 1. Developer interaction requirements

When extending this project:

- Prefer small, understandable phases.
- Explain what a file/function is responsible for.
- Avoid dumping an entire application at once.
- Keep functions reusable.
- Separate business/database operations from interface-specific code.
- Give exact file paths when asking the developer to add or edit code.
- When changing an existing function, state whether to replace the entire file or only a specific block.
- Do not assume knowledge of browser caching, Service Workers, IndexedDB, Django URL routing, or API architecture.
- Explain confusing naming when appropriate.
- Preserve plain Django + plain JavaScript unless there is a compelling future reason to change.
- Avoid React/Vue/etc. for this MVP.
- Avoid adding unnecessary infrastructure.

The developer requested a **hybrid pace**:

> Not too slow, but not a complete code dump either.

A good pattern is:

```text
Explain concept briefly
→ show exact file
→ provide small code change
→ explain resulting flow
→ ask/test before next major phase
```

---

# 2. Environment and stack

Ubuntu, Python, Django 6.1, PostgreSQL (`centcompras_db`, user `postgres`), plain HTML + JavaScript. No React/Vue. No Django REST Framework unless later requested.

Secrets belong in `config/settings.py` (gitignored) or environment variables — not in this file. See `config/settings.example.py`.

---

# 3. Live state — see handoff

Do **not** treat older copies of this document (offline catalogue, `branches` app, `add_product`, `/manage/products/`, `GET /api/products/`, typed `Product.stock`) as current.

Today (summary only):

- Apps: `accounts`, `products`, `procurement`, `inventory`, `logging_utils`. **No `branches/`.**
- Warehouse groups manage `/manage/items/`, `/manage/purchase-orders/`, `/manage/goods-receipts/`.
- Stock is a ledger (`StockMovement`) plus cached `Item.quantity`. Selling prices are manual; cost is `SupplierItemPrice`.
- CLI is `add_item`. Offline catalogue was **removed** (Phase 7 may re-add it).
- Next product phase: **manager catalog** (Phase 4). Branches and orders are later.

Seed logins: `warehouse.admin@centcompras.dev`, `warehouse.manager@centcompras.dev`, `warehouse.operator@centcompras.dev` (password `devpass123`). `/admin/` is superuser only.

Architecture to preserve:

```text
CLI / staff console / admin / API
        ↓
    services.py
        ↓
     models.py
        ↓
    PostgreSQL
```

---

# 4. What must NOT be silently added

Do not introduce the following without an explicit future phase/request:

- React, Vue, Angular
- Django REST Framework
- Celery, Redis, WebSockets, background workers
- Product creation from a branch/public UI
- Cloud deployment
- Stock reservation
- Complicated synchronization frameworks
- The tenancy-doc `Order` stub (`item_name`)
- Branches, orders, offline, or email while working on another phase

The developer wants to understand each layer before adding complexity.

---

# 5. Documentation philosophy

When explaining work, make the data path explicit.

```text
CLI → service → model → PostgreSQL
```

```text
browser → API → service → model → PostgreSQL
```

Many beginner confusions disappear once the direction and responsibility of each layer are shown.

---

# 6. Phase 7 notes (offline — not implemented)

The original MVP had a Service Worker (app shell) and IndexedDB (read-only catalogue cache). That layer was **deleted**. If Phase 7 re-adds it:

- PostgreSQL remains the source of truth. IndexedDB is a last-known catalogue copy, not a warehouse database.
- `saveProducts` (or equivalent) means **cache the downloaded catalogue**, not insert items into PostgreSQL.
- Service Worker cache = the app shell. IndexedDB = the data. Do not cache `/api/` in the worker.
- Use one origin (`localhost` or `127.0.0.1`, not both).
- Cached stock is last-known, not real-time.
- Offline **orders** (client UUID, pending store, idempotent retry) wait until branches exist. Do not start that here.

---

# 7. Main instruction to the next coding agent

Continue this project **incrementally**.

Do not optimize away the learning process.

Before adding a substantial new subsystem, explain:

```text
what problem it solves
where it belongs
what file(s) are added or changed
what function calls what
how to test it
```

Then implement only that phase.

The correct outcome is not merely:

> It works.

The desired outcome is:

> It works, and the developer understands why.
