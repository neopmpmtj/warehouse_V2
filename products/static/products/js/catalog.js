const CATALOG_API = "/api/manage/catalog/";
const FAMILY_API = "/api/manage/families/";
const THEME_KEY = "cc-theme";
const LANG_KEY = "cc-lang";

function safeGetStorage(key, fallback) {
    try {
        return localStorage.getItem(key) || fallback;
    } catch (error) {
        return fallback;
    }
}

function safeSetStorage(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (error) {
        /* ignore */
    }
}

const state = {
    items: [],
    families: [],
    search: "",
    familyId: "",
    belowReorderOnly: false,
};

function currentLang() {
    return safeGetStorage(LANG_KEY, "en");
}

function currentTheme() {
    return safeGetStorage(THEME_KEY, "light");
}

function t(key, vars) {
    const dict = CATALOG_I18N[currentLang()] || CATALOG_I18N.en;
    let text = dict[key] || CATALOG_I18N.en[key] || key;
    if (vars) {
        Object.entries(vars).forEach(([name, value]) => {
            text = text.replaceAll(`{${name}}`, String(value));
        });
    }
    return text;
}

function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
}

async function api(path, options) {
    const response = await fetch(path, {
        credentials: "same-origin",
        ...options,
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            ...(options && options.headers),
        },
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || t("errorGeneric"));
    }
    return payload;
}

function formatQty(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const s = String(value);
    const dot = s.indexOf(".");
    if (dot === -1) {
        return s;
    }
    const intPart = s.slice(0, dot);
    const frac = s.slice(dot + 1).replace(/0+$/, "");
    return frac ? intPart + "." + frac : intPart;
}

function formatCost(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const s = String(value);
    const dot = s.indexOf(".");
    if (dot === -1) {
        return s + ".00";
    }
    const intPart = s.slice(0, dot);
    const frac = (s.slice(dot + 1) + "00").slice(0, 2);
    return intPart + "." + frac;
}

let bannerTimer = null;

function showBanner(message, isError) {
    const banner = document.getElementById("banner");
    banner.hidden = false;
    banner.textContent = message;
    banner.classList.toggle("is-error", Boolean(isError));
    if (bannerTimer) {
        window.clearTimeout(bannerTimer);
    }
    bannerTimer = window.setTimeout(clearBanner, 5000);
}

function clearBanner() {
    if (bannerTimer) {
        window.clearTimeout(bannerTimer);
        bannerTimer = null;
    }
    const banner = document.getElementById("banner");
    banner.hidden = true;
    banner.textContent = "";
}

function applyStaticI18n() {
    document.documentElement.lang = currentLang();
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
    const themeButton = document.getElementById("theme-toggle");
    if (themeButton) {
        themeButton.textContent = currentTheme() === "dark" ? t("themeLight") : t("themeDark");
    }
}

function setTheme(theme) {
    safeSetStorage(THEME_KEY, theme);
    document.documentElement.setAttribute("data-theme", theme);
    applyStaticI18n();
}

function setLanguage(lang) {
    safeSetStorage(LANG_KEY, lang);
    applyStaticI18n();
    fillFamilyFilter();
    renderCatalog();
}

function fillSelect(select, options) {
    const current = select.value;
    select.replaceChildren();
    options.forEach((option) => {
        const node = document.createElement("option");
        node.value = option.value;
        node.textContent = option.label;
        select.appendChild(node);
    });
    if ([...select.options].some((option) => option.value === current)) {
        select.value = current;
    }
}

function textTd(value) {
    const td = document.createElement("td");
    td.textContent = value;
    return td;
}

function filteredItems() {
    let rows = state.items;
    if (state.familyId) {
        rows = rows.filter((item) => String(item.family.id) === state.familyId);
    }
    if (state.belowReorderOnly) {
        rows = rows.filter((item) => item.below_reorder);
    }
    const query = state.search.trim().toLowerCase();
    if (query) {
        rows = rows.filter(
            (item) =>
                (item.internal_code || "").toLowerCase().includes(query) ||
                item.description.toLowerCase().includes(query)
        );
    }
    return rows;
}

function renderSuppliers(item) {
    if (!item.suppliers || !item.suppliers.length) {
        return t("noSuppliers");
    }
    return item.suppliers
        .map((supplier) => (supplier.primary ? `${supplier.name} ★` : supplier.name))
        .join(", ");
}

function renderCatalog() {
    const body = document.getElementById("catalog-body");
    body.replaceChildren();
    const rows = filteredItems();

    const emptyNote = document.getElementById("catalog-empty");
    emptyNote.hidden = rows.length > 0;
    emptyNote.textContent = t(state.items.length === 0 ? "empty" : "noMatch");

    rows.forEach((item) => {
        const row = document.createElement("tr");
        if (item.below_reorder) {
            row.classList.add("row-warn");
        }

        row.appendChild(textTd(item.internal_code || "—"));
        row.appendChild(textTd(item.description));
        row.appendChild(textTd(item.family.name));
        row.appendChild(textTd(item.unit_of_measure || "—"));
        row.appendChild(textTd(formatQty(item.quantity)));
        row.appendChild(textTd(formatQty(item.reorder_level)));
        row.appendChild(textTd(formatCost(item.buying_price)));
        row.appendChild(textTd(formatCost(item.retail_price)));
        row.appendChild(textTd(formatCost(item.wholesale_price)));
        row.appendChild(textTd(formatCost(item.special_price)));
        row.appendChild(textTd(renderSuppliers(item)));

        const status = document.createElement("td");
        const pill = document.createElement("span");
        pill.className = item.below_reorder ? "pill pill-warn" : "pill pill-ok";
        pill.textContent = t(item.below_reorder ? "statusBelowReorder" : "statusOk");
        status.appendChild(pill);
        row.appendChild(status);

        body.appendChild(row);
    });
}

async function loadCatalog() {
    const data = await api(CATALOG_API);
    state.items = data.catalog;
    renderCatalog();
}

async function loadFamilies() {
    const data = await api(FAMILY_API);
    state.families = data.families;
    fillFamilyFilter();
}

function fillFamilyFilter() {
    const select = document.getElementById("catalog-family");
    fillSelect(select, [
        { value: "", label: t("allFamilies") },
        ...state.families.map((family) => ({
            value: String(family.id),
            label: family.name,
        })),
    ]);
    select.value = state.familyId || "";
}

function bindEvents() {
    document.getElementById("language-select").value = currentLang();
    document.getElementById("language-select").addEventListener("change", (event) => {
        setLanguage(event.target.value);
    });
    document.getElementById("theme-toggle").addEventListener("click", () => {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
    });

    document.getElementById("catalog-search").addEventListener("input", (event) => {
        state.search = event.target.value;
        renderCatalog();
    });
    document.getElementById("catalog-family").addEventListener("change", (event) => {
        state.familyId = event.target.value;
        renderCatalog();
    });
    document.getElementById("catalog-below-reorder").addEventListener("change", (event) => {
        state.belowReorderOnly = event.target.checked;
        renderCatalog();
    });
}

async function init() {
    applyStaticI18n();
    bindEvents();
    try {
        await Promise.all([loadCatalog(), loadFamilies()]);
    } catch (error) {
        showBanner(error.message || t("loadFailed"), true);
    }
}

init();
