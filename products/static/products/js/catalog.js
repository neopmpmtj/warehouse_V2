const CATALOG_API = "/api/manage/catalog/";
const FAMILY_API = "/api/manage/families/";
const SUBFAMILY_API = "/api/manage/sub-families/";
const THEME_KEY = "cc-theme";
const LANG_KEY = "cc-lang";
const NUMERIC_SORT_KEYS = new Set([
    "quantity",
    "reserved",
    "available",
    "reorder_level",
    "buying_price",
    "retail_price",
    "wholesale_price",
    "special_price",
]);

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
    subFamilies: [],
    search: "",
    familyId: "",
    subFamilyId: "",
    belowReorderOnly: false,
    includeInactive: false,
    sortKey: "description",
    sortDir: "asc",
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
    updateSortHeaders();
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
    fillSubFamilyFilter();
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

function subFamilyFamilyId(subFamily) {
    if (subFamily.family && subFamily.family.id != null) {
        return subFamily.family.id;
    }
    return subFamily.family_id;
}

function familyLabel(family) {
    if (state.includeInactive && !family.is_active) {
        return `${family.name} (${t("inactive")})`;
    }
    return family.name;
}

function subFamilyLabel(subFamily, familyId) {
    const name =
        state.includeInactive && !subFamily.is_active
            ? `${subFamily.name} (${t("inactive")})`
            : subFamily.name;
    if (familyId) {
        return name;
    }
    const familyName = subFamily.family ? subFamily.family.name : "";
    return `${familyName} / ${name}`;
}

function statusLabel(item) {
    if (!item.is_active) {
        return t("statusInactive");
    }
    return item.below_reorder ? t("statusBelowReorder") : t("statusOk");
}

function filteredItems() {
    let rows = state.items;
    if (state.familyId) {
        rows = rows.filter((item) => String(item.family.id) === state.familyId);
    }
    if (state.subFamilyId) {
        rows = rows.filter(
            (item) => item.sub_family && String(item.sub_family.id) === state.subFamilyId
        );
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

function numericSortValue(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }
    return Number(value);
}

function sortValue(item, key) {
    switch (key) {
        case "internal_code":
            return item.internal_code || "";
        case "description":
            return item.description;
        case "family":
            return item.family.name;
        case "sub_family":
            return item.sub_family ? item.sub_family.name : "";
        case "unit_of_measure":
            return item.unit_of_measure || "";
        case "quantity":
            return numericSortValue(item.quantity);
        case "reserved":
            return numericSortValue(item.reserved);
        case "available":
            return numericSortValue(item.available);
        case "reorder_level":
            return numericSortValue(item.reorder_level);
        case "buying_price":
            return numericSortValue(item.buying_price);
        case "retail_price":
            return numericSortValue(item.retail_price);
        case "wholesale_price":
            return numericSortValue(item.wholesale_price);
        case "special_price":
            return numericSortValue(item.special_price);
        case "suppliers":
            return renderSuppliers(item);
        case "status":
            return statusLabel(item);
        default:
            return item.id;
    }
}

function compareItems(left, right, key, dir) {
    const leftVal = sortValue(left, key);
    const rightVal = sortValue(right, key);
    let cmp = 0;
    if (NUMERIC_SORT_KEYS.has(key)) {
        if (leftVal === null && rightVal === null) {
            cmp = 0;
        } else if (leftVal === null) {
            cmp = 1;
        } else if (rightVal === null) {
            cmp = -1;
        } else {
            cmp = leftVal - rightVal;
        }
    } else {
        cmp = String(leftVal).localeCompare(String(rightVal), currentLang(), {
            sensitivity: "base",
        });
    }
    if (cmp === 0) {
        cmp = left.id - right.id;
    }
    return dir === "desc" ? -cmp : cmp;
}

function sortedItems(rows) {
    if (!state.sortKey) {
        return [...rows].sort((left, right) => left.id - right.id);
    }
    return [...rows].sort((left, right) =>
        compareItems(left, right, state.sortKey, state.sortDir)
    );
}

function updateSortHeaders() {
    document.querySelectorAll(".page .grid th[data-sort]").forEach((header) => {
        const key = header.getAttribute("data-sort");
        const columnKey = header.getAttribute("data-i18n-col");
        const columnLabel = columnKey ? t(columnKey) : key;
        const button = header.querySelector(".sort-btn");
        const indicator = header.querySelector(".sort-indicator");
        if (!button || !indicator) {
            return;
        }
        if (state.sortKey === key) {
            header.setAttribute("aria-sort", state.sortDir === "asc" ? "ascending" : "descending");
            header.classList.add("is-sorted");
            indicator.textContent = state.sortDir === "asc" ? "▲" : "▼";
            button.setAttribute(
                "aria-label",
                t(state.sortDir === "asc" ? "sortActiveAsc" : "sortActiveDesc", {
                    column: columnLabel,
                })
            );
            return;
        }
        header.setAttribute("aria-sort", "none");
        header.classList.remove("is-sorted");
        indicator.textContent = "";
        button.setAttribute("aria-label", t("sortBy", { column: columnLabel }));
    });
}

function toggleSort(key) {
    if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        return;
    }
    state.sortKey = key;
    state.sortDir = "asc";
}

function renderCatalog() {
    const body = document.getElementById("catalog-body");
    body.replaceChildren();
    const rows = sortedItems(filteredItems());

    const emptyNote = document.getElementById("catalog-empty");
    emptyNote.hidden = rows.length > 0;
    emptyNote.textContent = t(state.items.length === 0 ? "empty" : "noMatch");

    rows.forEach((item) => {
        const row = document.createElement("tr");
        if (!item.is_active || !item.family.is_active) {
            row.classList.add("is-inactive");
        } else if (item.below_reorder) {
            row.classList.add("row-warn");
        }

        row.appendChild(textTd(item.internal_code || "—"));
        row.appendChild(textTd(item.description));
        row.appendChild(textTd(familyLabel(item.family)));
        row.appendChild(textTd(item.sub_family ? subFamilyLabel(item.sub_family, state.familyId) : "—"));
        row.appendChild(textTd(item.unit_of_measure || "—"));
        row.appendChild(textTd(formatQty(item.quantity)));
        row.appendChild(textTd(formatQty(item.reserved)));
        row.appendChild(textTd(formatQty(item.available)));
        row.appendChild(textTd(formatQty(item.reorder_level)));
        row.appendChild(textTd(formatCost(item.buying_price)));
        row.appendChild(textTd(formatCost(item.retail_price)));
        row.appendChild(textTd(formatCost(item.wholesale_price)));
        row.appendChild(textTd(formatCost(item.special_price)));
        row.appendChild(textTd(renderSuppliers(item)));

        const status = document.createElement("td");
        const pill = document.createElement("span");
        if (!item.is_active) {
            pill.className = "pill pill-muted";
            pill.textContent = t("statusInactive");
        } else if (item.below_reorder) {
            pill.className = "pill pill-warn";
            pill.textContent = t("statusBelowReorder");
        } else {
            pill.className = "pill pill-ok";
            pill.textContent = t("statusOk");
        }
        status.appendChild(pill);
        row.appendChild(status);

        body.appendChild(row);
    });
    updateSortHeaders();
}

function catalogApiUrl() {
    const params = new URLSearchParams();
    if (state.includeInactive) {
        params.set("include_inactive", "1");
    }
    const query = params.toString();
    return query ? `${CATALOG_API}?${query}` : CATALOG_API;
}

async function loadCatalog() {
    const data = await api(catalogApiUrl());
    state.items = data.catalog;
    renderCatalog();
}

async function loadFamilies() {
    const data = await api(FAMILY_API);
    state.families = data.families;
    fillFamilyFilter();
}

async function loadSubFamilies() {
    const data = await api(SUBFAMILY_API);
    state.subFamilies = data.sub_families || [];
    fillSubFamilyFilter();
}

function fillFamilyFilter() {
    const select = document.getElementById("catalog-family");
    fillSelect(select, [
        { value: "", label: t("allFamilies") },
        ...state.families.map((family) => ({
            value: String(family.id),
            label: familyLabel(family),
        })),
    ]);
    select.value = state.familyId || "";
}

function fillSubFamilyFilter() {
    const select = document.getElementById("catalog-sub-family");
    const familyId = state.familyId;
    const rows = state.subFamilies.filter((subFamily) => {
        if (!familyId) {
            return true;
        }
        return String(subFamilyFamilyId(subFamily)) === familyId;
    });
    fillSelect(select, [
        { value: "", label: t("allSubFamilies") },
        ...rows.map((subFamily) => ({
            value: String(subFamily.id),
            label: subFamilyLabel(subFamily, familyId),
        })),
    ]);
    if (
        state.subFamilyId &&
        rows.some((subFamily) => String(subFamily.id) === state.subFamilyId)
    ) {
        select.value = state.subFamilyId;
    } else {
        select.value = "";
        state.subFamilyId = "";
    }
}

function bindEvents() {
    const langSelect = document.getElementById("language-select");
    if (langSelect) {
        langSelect.value = currentLang();
        langSelect.addEventListener("change", (event) => {
            setLanguage(event.target.value);
        });
    }
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            setTheme(currentTheme() === "dark" ? "light" : "dark");
        });
    }

    document.getElementById("catalog-search").addEventListener("input", (event) => {
        state.search = event.target.value;
        renderCatalog();
    });
    document.getElementById("catalog-family").addEventListener("change", (event) => {
        state.familyId = event.target.value;
        fillSubFamilyFilter();
        renderCatalog();
    });
    document.getElementById("catalog-sub-family").addEventListener("change", (event) => {
        state.subFamilyId = event.target.value;
        renderCatalog();
    });
    document.getElementById("catalog-below-reorder").addEventListener("change", (event) => {
        state.belowReorderOnly = event.target.checked;
        renderCatalog();
    });
    document.getElementById("catalog-include-inactive").addEventListener("change", async (event) => {
        state.includeInactive = event.target.checked;
        fillFamilyFilter();
        fillSubFamilyFilter();
        try {
            await loadCatalog();
        } catch (error) {
            showBanner(error.message || t("loadFailed"), true);
        }
    });

    const sortableHead = document.querySelector(".page .grid thead");
    if (sortableHead) {
        sortableHead.addEventListener("click", (event) => {
            const button = event.target.closest("th[data-sort] .sort-btn");
            if (!button) {
                return;
            }
            const key = button.closest("th").getAttribute("data-sort");
            toggleSort(key);
            renderCatalog();
        });
    }
}

async function init() {
    applyStaticI18n();
    bindEvents();
    try {
        await Promise.all([loadCatalog(), loadFamilies(), loadSubFamilies()]);
    } catch (error) {
        showBanner(error.message || t("loadFailed"), true);
    }
}

init();
