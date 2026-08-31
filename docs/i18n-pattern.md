# CentCompras — Dual-language UI pattern (EN + pt-PT)

> **Audience:** developers and coding agents porting or extending CentCompras, or replicating the same bilingual setup in a new project.
>
> **Last updated:** 31 August 2026.

This document describes how CentCompras implements **English + Portuguese (Portugal)** in the staff and branch consoles. The UI is **not** translated with Django gettext `.po` files. Translation lives in **vanilla JavaScript dictionaries** applied at runtime in the browser.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3, **Django 6.1**, PostgreSQL |
| Frontend | Django HTML templates + **plain JavaScript** (no React/Vue) |
| UI i18n | Custom JS objects (`*_i18n.js`) + `data-i18n*` attributes |
| Preference storage | Browser `localStorage` |
| User manuals | Markdown (+ PDF when built) under `docs/user-manuals/en/` and `docs/user-manuals/pt/` |

Django settings (`config/settings/base.py`) set `USE_I18N = True` and `LANGUAGE_CODE = "en-gb"`, but **server-rendered pages do not switch locale**. Templates ship English fallback text; JavaScript replaces visible strings after load.

---

## Supported languages

| UI code | Meaning | `document.documentElement.lang` |
|---------|---------|----------------------------------|
| `en` | English (default) | `en` |
| `pt` | Portuguese (Portugal) | `pt-PT` |

The dashboard language `<select>` stores `en` or `pt`. Older code stored `pt-PT`; all readers **normalize** any value starting with `pt` to `pt`.

```javascript
function normalizeLang(raw) {
    if (raw && String(raw).toLowerCase().startsWith("pt")) {
        return "pt";
    }
    return "en";
}
```

Console dictionaries are keyed as `"pt-PT"`. Add an alias so both codes work:

```javascript
CONSOLE_I18N.pt = CONSOLE_I18N["pt-PT"];
```

---

## Architecture overview

```text
┌─────────────────────────────────────────────────────────────┐
│  Dashboard (preferences bar)                                 │
│  <select id="pref-language">  →  localStorage["cc-lang"]    │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   item_console      purchase_orders    branch/catalog
         │                 │                 │
         ▼                 ▼                 ▼
   console_i18n.js   purchase_orders_i18n.js   (inline or module dict)
         │                 │                 │
         └──────── t(key) ──┴── apiErrorMessage(code) ──┘
                           │
                           ▼
              data-i18n / data-i18n-placeholder / data-i18n-aria
```

**Decision D38 (dashboard vs work-page chrome):** language and theme controls live on **dashboards** (`preferences_bar.html`). Work/console pages **read** the stored preference but do not expose their own language selector (legacy `#language-select` in Settings was removed).

---

## localStorage keys

| Key | Values | Purpose |
|-----|--------|---------|
| `cc-lang` | `en` \| `pt` | Active UI language |
| `cc-theme` | `light` \| `dark` | Active colour theme |

Both keys are shared across warehouse dashboards, branch dashboards, and all console/work pages. A choice on the dashboard applies immediately on navigation.

Always read/write through safe wrappers — storage may be blocked:

```javascript
function safeGet(key, fallback) {
    try {
        return localStorage.getItem(key) || fallback;
    } catch (error) {
        return fallback;
    }
}
```

On language change, dispatch a custom event so other scripts (e.g. help links) can react:

```javascript
document.dispatchEvent(new CustomEvent("cc-lang-changed"));
```

---

## Reference files (copy these patterns)

| Role | Path |
|------|------|
| Dashboard language selector HTML | `products/templates/products/includes/preferences_bar.html` |
| Dashboard i18n + theme bar | `products/static/products/js/preferences_bar.js` |
| Largest console dictionary | `products/static/products/js/console_i18n.js` |
| Console `t()`, `applyStaticI18n()`, API errors | `products/static/products/js/console.js` |
| Help/manual launcher (lang-aware) | `products/static/products/js/console_settings_menu.js` |
| Early `<head>` anti-flash script | `products/templates/products/dashboard.html` (lines 8–25) |
| Warehouse dashboard example | `products/templates/products/dashboard.html` |
| Branch dashboard example | `branches/templates/branches/dashboard.html` |

### Per-page `*_i18n.js` modules

| Page / feature | Dictionary file |
|----------------|-----------------|
| Item console | `products/static/products/js/console_i18n.js` |
| Manager catalog | `products/static/products/js/catalog_i18n.js` |
| Cost trends | `products/static/products/js/cost_trends_i18n.js` |
| Purchase orders | `procurement/static/procurement/js/purchase_orders_i18n.js` |
| Goods receipts | `inventory/static/inventory/js/goods_receipts_i18n.js` |
| Company Voice feed | `company_voice/static/company_voice/js/feed_i18n.js` |

Some smaller features (e.g. request threads) embed a compact `I18N` object inline in the template instead of a separate file — same shape, same `t()` pattern.

---

## Implementation recipe for a new page

### 1. Create the dictionary

```javascript
// static/myapp/js/my_page_i18n.js
const MY_PAGE_I18N = {
    en: {
        title: "My page",
        save: "Save",
        errorGeneric: "Something went wrong.",
        duplicate_name: 'Name "{name}" already exists.',
    },
    "pt-PT": {
        title: "A minha página",
        save: "Guardar",
        errorGeneric: "Ocorreu um erro.",
        duplicate_name: 'O nome "{name}" já existe.',
    },
};
MY_PAGE_I18N.pt = MY_PAGE_I18N["pt-PT"];
```

Keep **error-code keys** identical to the stable `code` strings returned by the Django service/API layer (snake_case). User manuals (`docs/user-manuals/en/…`) document the exact server text; mirror constraints in `docs/user-manuals/pt/…` when behaviour changes.

### 2. Add lookup helpers in the page script

```javascript
const LANG_KEY = "cc-lang";

function currentLang() {
    const raw = safeGet(LANG_KEY, "en");
    return String(raw).toLowerCase().startsWith("pt") ? "pt" : "en";
}

function t(key, vars) {
    const dict = MY_PAGE_I18N[currentLang()] || MY_PAGE_I18N.en;
    let text = dict[key] || MY_PAGE_I18N.en[key] || key;
    if (vars) {
        Object.entries(vars).forEach(([name, value]) => {
            text = text.replaceAll(`{${name}}`, String(value));
        });
    }
    return text;
}
```

For modules that use the `pt-PT` key directly (not normalized to `pt`), index with `MY_PAGE_I18N[currentLang()]` only after aliasing `pt`.

### 3. Mark up the template

Use **English fallback text** in HTML so the page is readable before JS runs:

```html
<h1 data-i18n="title">My page</h1>
<input data-i18n-placeholder="searchPlaceholder" placeholder="Search…">
<button data-i18n-aria="settingsAria" aria-label="Settings">…</button>
```

Supported attributes in this codebase:

| Attribute | Applies to |
|-----------|------------|
| `data-i18n` | `textContent` |
| `data-i18n-placeholder` | `placeholder` |
| `data-i18n-aria` | `aria-label` |
| `data-i18n-col` | Table column headers (some consoles) |

### 4. Apply on load and on language change

```javascript
function applyStaticI18n() {
    const lang = currentLang();
    document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
    document.title = `${t("title")} — CentCompras`;
    document.querySelectorAll("[data-i18n]").forEach((node) => {
        node.textContent = t(node.getAttribute("data-i18n"));
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
        node.setAttribute("placeholder", t(node.getAttribute("data-i18n-placeholder")));
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
        node.setAttribute("aria-label", t(node.getAttribute("data-i18n-aria")));
    });
}
```

Re-run `applyStaticI18n()` and any dynamic renderers (`renderTable()`, etc.) when language changes. Listen for `cc-lang-changed` if the page does not own the selector.

### 5. Early `<head>` script (prevent flash)

Every themed/i18n page should set `lang` and `data-theme` before CSS paints:

```html
<script>
(function () {
    var theme = "light";
    var lang = "en";
    try {
        theme = localStorage.getItem("cc-theme") || "light";
        lang = localStorage.getItem("cc-lang") || "en";
    } catch (e) { /* blocked storage */ }
    if (String(lang).toLowerCase().indexOf("pt") === 0) {
        lang = "pt-PT";
    } else {
        lang = "en";
    }
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.setAttribute("lang", lang);
})();
</script>
```

Load `preferences_bar.js` only on **dashboard** templates, not on every work page.

### 6. Wire scripts in the template

```html
<script src="{% static 'myapp/js/my_page_i18n.js' %}?v=1"></script>
<script src="{% static 'myapp/js/my_page.js' %}?v=1"></script>
```

**Cache-buster rule:** if you change any static JS/CSS file, bump `?v=` in **every** template that references it (see `AGENTS.md` → Frontend / static assets).

---

## API error translation

Services raise validation errors with a stable machine-readable **`code`** (and usually an English `error` / `message` for logs and EN fallback). The client maps `code` → dictionary entry:

```javascript
function apiErrorMessage(payload) {
    const fallback = payload.error || t("errorGeneric");
    const code = payload.code;
    if (!code) {
        return fallback;
    }
    const localized = t(code);
    if (!localized || localized === code) {
        return fallback;
    }
    if (!localized.includes("{name}")) {
        if (currentLang() === "en" && payload.error) {
            return payload.error;
        }
        return localized;
    }
    // interpolate {name}, etc. from payload fields
    return t(code, payload);
}
```

**Convention:** keep server `code` strings in **snake_case English** (e.g. `duplicate_family_name`, `internal_code_required`). Add the same key to both `en` and `pt-PT` blocks in the relevant `*_i18n.js`.

---

## Dates, numbers, and currency

Use `Intl` via `toLocaleString` with locale tied to the active language:

```javascript
const locale = currentLang() === "pt" ? "pt-PT" : "en-GB";
amount.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
date.toLocaleString(locale, {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
});
```

---

## Help / user manuals

In-app Help (settings menu) resolves manuals by active language:

```text
/docs/user-manuals/{en|pt}/{slug}.pdf   ← preferred
/docs/user-manuals/{en|pt}/{slug}.md    ← fallback if PDF missing
```

Fallback order: current language → English. See `console_settings_menu.js` (`manualUrl`, `openHelp`).

Authoritative prose manuals live in:

- `docs/user-manuals/en/`
- `docs/user-manuals/pt/`

When changing validation rules or error messages, update **both** trees (see `.cursor/rules/user-manuals.mdc`).

---

## Theme (paired with language on dashboards)

`preferences_bar.js` also toggles `cc-theme` (`light` / `dark`) and sets `document.documentElement.dataset.theme`. Work pages read `cc-theme` in the early `<head>` script. Theme labels (`themeLight`, `themeDark`) live in the same dashboard dictionary as language strings.

---

## Checklist — new bilingual screen

- [ ] `*_i18n.js` with `en` and `pt-PT` (+ `pt` alias)
- [ ] Template English fallbacks + `data-i18n*` attributes
- [ ] `t()`, `applyStaticI18n()`, `currentLang()` in page JS
- [ ] Early `<head>` `cc-lang` / `cc-theme` read
- [ ] API error `code` keys added to dictionary (both languages)
- [ ] `toLocaleString` locale switches for formatted values
- [ ] Dynamic UI re-rendered on `cc-lang-changed` (if applicable)
- [ ] Bump `?v=` on any changed static asset in all templates
- [ ] `node --check` on edited JS files
- [ ] User-manual updates in `en/` and `pt/` if behaviour or messages changed

---

## Agent prompt (copy-paste for a new project)

```text
Implement the CentCompras dual-language UI pattern:

Stack: Django + PostgreSQL backend; plain HTML templates + vanilla JS (no SPA framework).

Languages: English (en) and Portuguese Portugal (pt, alias pt-PT).

Requirements:
1. localStorage keys: cc-lang (en|pt), cc-theme (light|dark).
2. One *_i18n.js per page/module: { en: {...}, "pt-PT": {...} }; set .pt = ["pt-PT"].
3. t(key, vars?) with English fallback and {name} interpolation.
4. Templates: English default text + data-i18n / data-i18n-placeholder / data-i18n-aria.
5. applyStaticI18n() on DOMContentLoaded; re-apply on language change.
6. Inline <head> script reads localStorage before paint (lang + data-theme).
7. Dashboard preferences bar: <select id="pref-language">; dispatch cc-lang-changed on change.
8. API errors: server returns stable code (snake_case); client translates via same dictionaries.
9. Dates/numbers: toLocaleString("pt-PT") or "en-GB" based on cc-lang.
10. User docs in docs/user-manuals/en/ and docs/user-manuals/pt/.

Do NOT use Django gettext .po files for console UI strings. Server stays English; the browser owns visible copy.

Reference: CentCompras docs/i18n-pattern.md and products/static/products/js/preferences_bar.js, console_i18n.js, console.js.
```

---

## What this pattern deliberately does **not** do

- **No Django template `{% trans %}`** for console copy — templates are English-only shells.
- **No `.po` / `locale/` catalogue** for the staff UI (Django `USE_I18N` is enabled but unused for these pages).
- **No per-user server-side locale** — preference is per-browser via `localStorage`, not the `User` model.
- **No automatic translation** — every string is hand-authored in both languages.

OAuth login views use `gettext_lazy` in one place (`accounts/google_views.py`); that is separate from the console i18n system described here.

---

## Related decisions

| ID | Topic |
|----|-------|
| D38 | Language/theme on dashboards only; work pages use sibling nav without a local language picker |
| User-manuals rule | `.cursor/rules/user-manuals.mdc` — when to update EN + pt-PT manuals |

For product sequencing and phase status, see `docs/handoff.md` and `docs/PROJECT-PLAN.md`.
