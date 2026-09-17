---
name: Branch i18n dictionaries
overview: "The cancel confirm is English because `/branch/requests/` JS never reads `cc-lang`. Fix it the same way catalog already does: JS dictionaries + `t()`, then apply that pattern to the other branch pages that still hardcode English."
todos:
  - id: requests-i18n
    content: Add branch_requests_i18n.js; t() all requests JS/HTML including cancel confirm; data-i18n on template
    status: pending
  - id: offline-sync-i18n
    content: Translate shared branch_offline.js banners and sync_queue last_error
    status: pending
  - id: receipts-threads-picker
    content: i18n /branch/receipts/, leftover thread placeholders, /branch/select/
    status: pending
  - id: cache-manuals-verify
    content: Bump ?v= + SW CACHE_NAME; update 04 EN/PT confirm copy; node --check + tests; PT UI check
    status: pending
isProject: false
---

# Translate branch JS with the existing i18n pattern

## Why the dialog is English

Chrome (Início / Catálogo / Pedidos) is already Portuguese: [`preferences_bar.js`](products/static/products/js/preferences_bar.js) reads `localStorage["cc-lang"]` and fills `[data-i18n]`.

The cancel **message** is built in [`orders/static/orders/js/branch_requests.js`](orders/static/orders/js/branch_requests.js) as a hardcoded English string:

```301:306:orders/static/orders/js/branch_requests.js
        return confirm(
            "Cancel internal request #" +
                requestId +
                " permanently? This cannot be undone."
        );
```

Same file hardcodes Submit, Add, Remove, Approve/Reject prompts, column headers, status text, and errors. The template [`orders/templates/orders/requests.html`](orders/templates/orders/requests.html) also has English markup (`Requests`, `New request`, `Status`, `Created`).

**Do not switch to Django `{% trans %}` / `.po` files.** The project already documents the global rule in [`docs/i18n-pattern.md`](docs/i18n-pattern.md): English HTML fallback + `en` / `pt-PT` JS dictionaries + `t(key, vars)` keyed off `cc-lang`. Branch catalog already follows this ([`branch_catalog_i18n.js`](branches/static/branches/js/branch_catalog_i18n.js) + `t()` in [`branch_catalog.js`](branches/static/branches/js/branch_catalog.js)).

Native `confirm()` **OK / Cancel** buttons stay in the **browser** language (English Chrome → English buttons). We translate our message. Replacing `confirm()` with a custom dialog is out of scope unless you ask for it.

## Where else this happens (branch)

| Surface | Today |
|---------|--------|
| `/branch/catalog/` | Already bilingual (`BRANCH_CATALOG_I18N`) |
| `/branch/threads/` | Mostly bilingual (inline `I18N`); leftover English placeholders (`Write a message…`) and `Request failed.` |
| `/branch/requests/` | **No dictionary** — the screenshot |
| `/branch/receipts/` | **No dictionary** — headings, buttons, `prompt("Reason for short-close:")`, `Request failed.` |
| Shared [`branch_offline.js`](branches/static/branches/js/branch_offline.js) | English offline banner + wrong-branch cache message (every `/branch/` page) |
| [`sync_queue.js`](branches/static/branches/js/sync_queue.js) | `"Sync failed."` |
| `/branch/select/` | Server-rendered English (`Select branch`, `Continue`) |

Warehouse consoles (items, POs, goods receipts, `/manage/internal-requests/`, warehouse threads) already have dictionaries. Leave them.

## How (copy catalog, do not invent a new system)

```text
cc-lang (pt|en) → currentLang() → BRANCH_*_I18N[lang] → t(key, {id: 11})
```

For `/branch/requests/`:

1. Add [`orders/static/orders/js/branch_requests_i18n.js`](orders/static/orders/js/branch_requests_i18n.js) (`en` + `pt-PT`, `pt` alias), same shape as catalog.
2. In `branch_requests.js`: `currentLang()` / `t(key, vars)` with `{id}` interpolation; every user-visible string goes through `t()` including `confirm(t("cancelConfirm", { id: req.id }))`.
3. Mark static HTML with `data-i18n` / `data-i18n-placeholder`; `applyStaticI18n()` on load and on `cc-lang-changed` (re-render list + detail).
4. Translate **status labels** (`draft` → Rascunho, `cancelled` → Cancelada, …), not the API values.
5. Map known API `code`s (`retail_price_missing`, `duplicate_request_line`, …) in the dict; fall back to `payload.error`.

PT for the confirm (exact UI string):

`Cancelar a requisição interna n.º {id} de forma permanente? Isto não pode ser anulado.`

Button: `Cancelar requisição interna`.

Shared offline strings: a small dict **inside** [`branch_offline.js`](branches/static/branches/js/branch_offline.js) (or a tiny `branch_offline_i18n.js`) so the banner on this page is Portuguese too.

Then the same recipe for receipts (extract inline script if needed, or keep inline `I18N` like threads) and the leftover thread placeholders / picker copy.

## Cache, manuals, tests

- Bump `branch_requests.js?v=8` → `?v=9` (and new i18n `?v=1`) in [`orders/templates/orders/requests.html`](orders/templates/orders/requests.html) and [`branches/templates/branches/service_worker.js`](branches/templates/branches/service_worker.js); bump `CACHE_NAME` `v16` → `v17`.
- Same `?v=` / SW bumps for any other changed branch shell JS.
- Manuals 04 EN+PT: confirm text is language-specific, not a single English sentence.
- `node --check` on edited JS; `branches` + `orders` tests (SW cache name).

## Verify

With `cc-lang=pt`, open `/branch/requests/`, click **Cancelar requisição interna**, confirm the dialog body is Portuguese. Spot-check receipts offline banner and catalog (no regression).
