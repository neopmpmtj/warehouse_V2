const API_ROOT = "/api/manage/items/";
const FAMILY_API = "/api/manage/families/";
const SUPPLIER_API = "/api/manage/suppliers/";
const SUPPLIER_PRICE_API = "/api/manage/supplier-prices/";
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
    suppliers: [],
    units: [],
    vat_rates: [],
    selectedIds: new Set(),
    editingId: null,
    sortKey: null,
    sortDir: "asc",
    page: 1,
    pageSize: 50,
    familyHistoryId: null,
    familyHistoryEntries: [],
    supplierHistoryId: null,
    supplierHistoryEntries: [],
    supplierPriceSupplierId: null,
    supplierPrices: [],
    busy: false,
};

let familyHistoryRequestId = 0;
let supplierHistoryRequestId = 0;
let itemHistoryRequestId = 0;
let supplierPriceRequestId = 0;
let itemSupplierPriceRequestId = 0;

const NUMERIC_SORT_KEYS = new Set(["reorder_level"]);

const LIFECYCLE_REASON = {
    GENESIS: "Genesis",
    TEMP_UNAVAILABLE: "Temporarily unavailable",
    DISCONTINUED: "No longer commercialized",
};

const LIFECYCLE_OTHER = "__other__";

const LIFECYCLE_PRESETS = {
    genesis: [{ value: LIFECYCLE_REASON.GENESIS, labelKey: "reasonGenesis" }],
    activate: [
        { value: LIFECYCLE_OTHER, labelKey: "reasonOther" },
    ],
    deactivate: [
        { value: LIFECYCLE_REASON.TEMP_UNAVAILABLE, labelKey: "reasonTempUnavailable" },
        { value: LIFECYCLE_REASON.DISCONTINUED, labelKey: "reasonDiscontinued" },
        { value: LIFECYCLE_OTHER, labelKey: "reasonOther" },
    ],
};

function currentLang() {
    return safeGetStorage(LANG_KEY, "en");
}

function currentTheme() {
    return safeGetStorage(THEME_KEY, "light");
}

function t(key, vars) {
    const dict = CONSOLE_I18N[currentLang()] || CONSOLE_I18N.en;
    let text = dict[key] || CONSOLE_I18N.en[key] || key;
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

function isBusy() {
    return state.busy;
}

function catalogPermissions() {
    const body = document.body;
    return {
        addItem: body.dataset.canAddItem === "true",
        changeItem: body.dataset.canChangeItem === "true",
        addFamily: body.dataset.canAddFamily === "true",
        changeFamily: body.dataset.canChangeFamily === "true",
        addSupplier: body.dataset.canAddSupplier === "true",
        changeSupplier: body.dataset.canChangeSupplier === "true",
        addSupplierItemPrice: body.dataset.canAddSupplierItemPrice === "true",
        changeSupplierItemPrice: body.dataset.canChangeSupplierItemPrice === "true",
    };
}

function applyCatalogPermissions(permissions) {
    if (!permissions) {
        return;
    }
    const body = document.body;
    body.dataset.canAddItem = permissions.add_item ? "true" : "false";
    body.dataset.canChangeItem = permissions.change_item ? "true" : "false";
    body.dataset.canAddFamily = permissions.add_family ? "true" : "false";
    body.dataset.canChangeFamily = permissions.change_family ? "true" : "false";
    body.dataset.canAddSupplier = permissions.add_supplier ? "true" : "false";
    body.dataset.canChangeSupplier = permissions.change_supplier ? "true" : "false";
    body.dataset.canAddSupplierItemPrice = permissions.add_supplier_item_price ? "true" : "false";
    body.dataset.canChangeSupplierItemPrice = permissions.change_supplier_item_price ? "true" : "false";
}

function canEditInternalCode(isNew, item) {
    if (isNew) {
        return true;
    }
    if (!item) {
        return false;
    }
    return !(item.internal_code || "").trim();
}

function setItemFormEditable(editable, isNew, item) {
    [
        "field-description",
        "field-family",
        "field-unit",
        "field-vat-rate",
        "field-reorder",
        "field-retail-price",
        "field-wholesale-price",
        "field-special-price",
        "field-reason",
    ].forEach((id) => {
        const field = document.getElementById(id);
        if (field) {
            field.disabled = !editable;
        }
    });
    const internalCodeField = document.getElementById("field-internal-code");
    if (internalCodeField) {
        const allowInternalCodeEdit = editable && canEditInternalCode(isNew, item);
        if (!allowInternalCodeEdit) {
            internalCodeField.disabled = true;
            internalCodeField.readOnly = Boolean(!isNew && item);
            internalCodeField.required = false;
        } else if (isNew) {
            internalCodeField.disabled = false;
            internalCodeField.readOnly = false;
            internalCodeField.required = true;
        } else {
            internalCodeField.disabled = false;
            internalCodeField.readOnly = false;
            internalCodeField.required = false;
        }
    }
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
    const themeButton = document.getElementById("theme-toggle");
    themeButton.textContent = currentTheme() === "dark" ? t("themeLight") : t("themeDark");
}

function setTheme(theme) {
    safeSetStorage(THEME_KEY, theme);
    document.documentElement.setAttribute("data-theme", theme);
    applyStaticI18n();
}

function setLanguage(lang) {
    safeSetStorage(LANG_KEY, lang);
    applyStaticI18n();
    fillFilterOptions();
    fillFormLookups();
    renderTable();
    renderFamilyTable();
    renderSupplierTable();
    refreshDrawerLabels();
    refreshEntityHistoryLabels();
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
        const mapped = payload.code ? t(payload.code) : "";
        const message = mapped && mapped !== payload.code
            ? mapped
            : (payload.error || t("errorGeneric"));
        throw new Error(message);
    }
    return payload;
}

function filteredItems() {
    const query = document.getElementById("search-input").value.trim().toLowerCase();
    const familyId = document.getElementById("family-filter").value;
    const status = document.getElementById("status-filter").value;
    const unit = document.getElementById("unit-filter").value;

    return state.items.filter((item) => {
        if (familyId && String(item.family.id) !== familyId) {
            return false;
        }
        if (status === "active" && !item.is_active) {
            return false;
        }
        if (status === "inactive" && item.is_active) {
            return false;
        }
        if (unit && item.unit_of_measure !== unit) {
            return false;
        }
        if (!query) {
            return true;
        }
        const haystack = `${item.internal_code} ${item.description} ${item.family.name}`.toLowerCase();
        return haystack.includes(query);
    });
}

function unitLabel(value) {
    return t(`unit.${value}`);
}

function sortValue(item, key) {
    switch (key) {
        case "internal_code":
            return item.internal_code || "";
        case "description":
            return item.description;
        case "family":
            return item.family.name;
        case "unit_of_measure":
            return unitLabel(item.unit_of_measure);
        case "reorder_level":
            return Number(item.reorder_level);
        case "vat_rate":
            return item.vat_rate ? item.vat_rate.label : "";
        case "status":
            return item.is_active ? t("active") : t("inactive");
        default:
            return item.id;
    }
}

function compareItems(left, right, key, dir) {
    const leftVal = sortValue(left, key);
    const rightVal = sortValue(right, key);
    let cmp = 0;
    if (NUMERIC_SORT_KEYS.has(key)) {
        cmp = leftVal - rightVal;
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
    return [...rows].sort((left, right) => compareItems(left, right, state.sortKey, state.sortDir));
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

function fillSelect(select, options, placeholder) {
    const current = select.value;
    select.replaceChildren();
    if (placeholder) {
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = placeholder;
        select.appendChild(empty);
    }
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

function fillFilterOptions() {
    fillSelect(
        document.getElementById("family-filter"),
        state.families.map((family) => ({
            value: String(family.id),
            label: family.is_active ? family.name : `${family.name} (${t("inactive")})`,
        })),
        t("allFamilies")
    );
    fillSelect(
        document.getElementById("unit-filter"),
        state.units.map((unit) => ({
            value: unit.value,
            label: unitLabel(unit.value),
        })),
        t("allUnits")
    );
}

function fillFormLookups() {
    const familySelect = document.getElementById("field-family");
    const selected = familySelect.value;
    const familyOptions = state.families
        .filter((family) => family.is_active || String(family.id) === selected)
        .map((family) => ({
            value: String(family.id),
            label: family.is_active ? family.name : `${family.name} (${t("inactive")})`,
        }));
    fillSelect(
        familySelect,
        familyOptions,
        familyOptions.length ? null : t("noFamilies")
    );
    fillSelect(
        document.getElementById("field-unit"),
        state.units.map((unit) => ({
            value: unit.value,
            label: unitLabel(unit.value),
        }))
    );
    fillSelect(
        document.getElementById("field-vat-rate"),
        state.vat_rates.map((vatRate) => ({
            value: String(vatRate.id),
            label: vatRate.label,
        }))
    );
}

function currentPageItems() {
    const full = sortedItems(filteredItems());
    const start = (state.page - 1) * state.pageSize;
    return {
        full,
        rows: full.slice(start, start + state.pageSize),
    };
}

function resetPage() {
    state.page = 1;
}

function renderPagination(total) {
    const prev = document.getElementById("items-prev");
    const next = document.getElementById("items-next");
    const label = document.getElementById("items-page-label");
    if (!prev || !next || !label) {
        return;
    }
    const numPages = Math.max(Math.ceil(total / state.pageSize), 1);
    label.textContent = t("pageOf", { page: state.page, pages: numPages });
    prev.disabled = state.page <= 1;
    next.disabled = state.page >= numPages;
}

function goToPage(page) {
    const numPages = Math.max(Math.ceil(filteredItems().length / state.pageSize), 1);
    if (page < 1 || page > numPages) {
        return;
    }
    state.page = page;
    renderTable();
}

function renderTable() {
    const body = document.getElementById("item-table-body");
    if (!body) {
        return;
    }
    const { full, rows } = currentPageItems();
    body.replaceChildren();

    document.getElementById("result-count").textContent = t("showingCount", {
        shown: full.length,
        total: state.items.length,
    });

    renderPagination(full.length);

    if (full.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 9;
        cell.className = "empty-row";
        cell.textContent = state.items.length === 0 ? t("empty") : t("noMatch");
        row.appendChild(cell);
        body.appendChild(row);
        updateSortHeaders();
        return;
    }

    const perms = catalogPermissions();
    rows.forEach((item) => {
        const row = document.createElement("tr");
        if (state.selectedIds.has(item.id)) {
            row.classList.add("is-selected");
        }
        if (!item.is_active) {
            row.classList.add("is-inactive");
        }

        const checkCell = document.createElement("td");
        checkCell.className = "col-check";
        if (perms.changeItem) {
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = state.selectedIds.has(item.id);
            checkbox.addEventListener("click", (event) => event.stopPropagation());
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    state.selectedIds.add(item.id);
                } else {
                    state.selectedIds.delete(item.id);
                }
                renderTable();
            });
            checkCell.appendChild(checkbox);
        }

        const code = document.createElement("td");
        code.textContent = item.internal_code || "—";

        const description = document.createElement("td");
        description.textContent = item.description;

        const family = document.createElement("td");
        family.textContent = item.family.name;

        const unit = document.createElement("td");
        unit.textContent = unitLabel(item.unit_of_measure);

        const reorder = document.createElement("td");
        reorder.textContent = item.reorder_level;

        const vatRate = document.createElement("td");
        vatRate.textContent = item.vat_rate ? item.vat_rate.label : "—";

        const status = document.createElement("td");
        const statusPill = document.createElement("span");
        statusPill.className = item.is_active ? "pill pill-ok" : "pill pill-muted";
        statusPill.textContent = item.is_active ? t("active") : t("inactive");
        status.appendChild(statusPill);

        const actions = document.createElement("td");
        actions.className = "row-actions";
        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "btn";
        openButton.textContent = perms.changeItem ? t("edit") : t("view");
        openButton.addEventListener("click", (event) => {
            event.stopPropagation();
            openDrawer(item);
        });
        actions.appendChild(openButton);
        if (perms.changeItem) {
            const lifeButton = document.createElement("button");
            lifeButton.type = "button";
            lifeButton.className = item.is_active ? "btn btn-danger" : "btn";
            lifeButton.textContent = item.is_active ? t("deactivate") : t("reactivate");
            lifeButton.addEventListener("click", (event) => {
                event.stopPropagation();
                toggleLifecycle(item);
            });
            actions.appendChild(lifeButton);
        }

        row.append(
            checkCell,
            code,
            description,
            family,
            unit,
            reorder,
            vatRate,
            status,
            actions
        );
        row.addEventListener("click", () => openDrawer(item));
        body.appendChild(row);
    });

    const visibleIds = rows.map((item) => item.id);
    const selectAll = document.getElementById("select-all");
    selectAll.checked = visibleIds.length > 0 && visibleIds.every((id) => state.selectedIds.has(id));
    updateSortHeaders();
}

function replaceItem(item) {
    const index = state.items.findIndex((entry) => entry.id === item.id);
    if (index === -1) {
        state.items.push(item);
        state.items.sort((left, right) => left.id - right.id);
        return;
    }
    state.items[index] = item;
}

function refreshDrawerLabels() {
    const drawer = document.getElementById("drawer");
    if (drawer.hidden) {
        return;
    }
    const perms = catalogPermissions();
    const isNew = !document.getElementById("field-id").value;
    const canSave = isNew ? perms.addItem : perms.changeItem;
    const item = isNew
        ? null
        : state.items.find((entry) => String(entry.id) === document.getElementById("field-id").value);
    document.getElementById("drawer-title").textContent = isNew
        ? t("drawerNew")
        : (perms.changeItem ? t("drawerEdit") : t("drawerView"));
    document.getElementById("item-save").hidden = !canSave;
    document.getElementById("reason-field").hidden = !canSave;
    document.getElementById("new-family-inline").hidden = !perms.addFamily;
    setItemFormEditable(canSave, isNew, item);
    const lifeButton = document.getElementById("drawer-lifecycle");
    if (isNew || !perms.changeItem) {
        lifeButton.hidden = true;
        return;
    }
    if (!item) {
        return;
    }
    lifeButton.hidden = false;
    lifeButton.textContent = item.is_active ? t("deactivate") : t("reactivate");
    lifeButton.className = item.is_active ? "btn btn-danger" : "btn";
}

function closeDrawer() {
    document.getElementById("drawer").hidden = true;
    document.getElementById("drawer-backdrop").hidden = true;
    state.editingId = null;
    itemSupplierPriceRequestId += 1;
    renderItemSupplierPrices([]);
}

function firstActiveFamilyId() {
    const family = state.families.find((item) => item.is_active);
    return family ? family.id : null;
}

function sortFamilies() {
    state.families.sort((left, right) =>
        left.name.localeCompare(right.name, currentLang(), { sensitivity: "base" })
    );
}

function replaceFamily(family) {
    const index = state.families.findIndex((item) => item.id === family.id);
    if (index === -1) {
        state.families.push(family);
    } else {
        state.families[index] = family;
    }
    sortFamilies();
    state.items.forEach((item) => {
        if (item.family.id === family.id) {
            item.family = {
                id: family.id,
                name: family.name,
                is_active: family.is_active,
            };
        }
    });
    fillFilterOptions();
    fillFormLookups();
    renderTable();
    renderFamilyTable();
}

function closeFamilyDrawer() {
    document.getElementById("family-drawer").hidden = true;
    document.getElementById("family-drawer-backdrop").hidden = true;
    resetFamilyHistory();
}

function closeSupplierDrawer() {
    document.getElementById("supplier-drawer").hidden = true;
    document.getElementById("supplier-drawer-backdrop").hidden = true;
    resetSupplierHistory();
}

async function openFamilyDrawer() {
    closeDrawer();
    closeSupplierDrawer();
    document.getElementById("family-drawer").hidden = false;
    document.getElementById("family-drawer-backdrop").hidden = false;
    try {
        const data = await api(FAMILY_API);
        state.families = data.families;
        sortFamilies();
        fillFilterOptions();
        fillFormLookups();
        renderFamilyTable();
        resetFamilyHistory();
    } catch (error) {
        showBanner(error.message, true);
        renderFamilyTable();
    }
}

function renderFamilyTable() {
    const body = document.getElementById("family-table-body");
    if (!body) {
        return;
    }
    body.replaceChildren();
    if (!state.families.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "empty-row";
        cell.textContent = t("emptyFamilies");
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }
    state.families.forEach((family) => {
        const row = document.createElement("tr");
        if (!family.is_active) {
            row.classList.add("is-inactive");
        }

        const name = document.createElement("td");
        name.textContent = family.name;

        const count = document.createElement("td");
        count.textContent = String(family.item_count ?? 0);

        const status = document.createElement("td");
        const pill = document.createElement("span");
        pill.className = family.is_active ? "pill pill-ok" : "pill pill-muted";
        pill.textContent = family.is_active ? t("active") : t("inactive");
        status.appendChild(pill);

        const actions = document.createElement("td");
        actions.className = "row-actions";
        const perms = catalogPermissions();
        if (perms.changeFamily) {
            const lifecycle = document.createElement("button");
            lifecycle.type = "button";
            lifecycle.className = family.is_active ? "btn btn-danger" : "btn";
            lifecycle.textContent = family.is_active ? t("deactivate") : t("reactivate");
            lifecycle.addEventListener("click", () => toggleFamilyActive(family));
            actions.appendChild(lifecycle);
        }
        const history = document.createElement("button");
        history.type = "button";
        history.className = "btn";
        history.textContent = t("history");
        history.addEventListener("click", () => loadFamilyHistory(family));
        actions.appendChild(history);

        row.append(name, count, status, actions);
        body.appendChild(row);
    });
}

function askFamilyName(options) {
    return new Promise((resolve) => {
        const backdrop = document.getElementById("family-name-dialog-backdrop");
        const dialog = document.getElementById("family-name-dialog");
        const title = document.getElementById("family-name-dialog-title");
        const help = document.getElementById("family-name-dialog-help");
        const input = document.getElementById("family-name-input");
        const error = document.getElementById("family-name-error");
        const confirmButton = document.getElementById("family-name-confirm");
        const cancelButton = document.getElementById("family-name-cancel");

        title.textContent = t(options.titleKey);
        if (options.helpKey) {
            help.textContent = t(options.helpKey);
            help.hidden = false;
        } else {
            help.hidden = true;
        }
        confirmButton.textContent = t(options.confirmKey || "save");
        input.value = options.initial || "";
        error.hidden = true;
        backdrop.hidden = false;
        dialog.hidden = false;
        input.focus();
        input.select();

        function finish(value) {
            backdrop.hidden = true;
            dialog.hidden = true;
            confirmButton.removeEventListener("click", onConfirm);
            cancelButton.removeEventListener("click", onCancel);
            backdrop.removeEventListener("click", onCancel);
            input.removeEventListener("keydown", onKey);
            resolve(value);
        }

        function onConfirm() {
            const name = input.value.trim();
            if (!name) {
                error.textContent = t("family_name_required");
                error.hidden = false;
                input.focus();
                return;
            }
            finish(name);
        }

        function onCancel() {
            finish(null);
        }

        function onKey(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                onConfirm();
            }
            if (event.key === "Escape") {
                onCancel();
            }
        }

        confirmButton.addEventListener("click", onConfirm);
        cancelButton.addEventListener("click", onCancel);
        backdrop.addEventListener("click", onCancel);
        input.addEventListener("keydown", onKey);
    });
}

async function promptCreateFamily(showHelp) {
    if (!catalogPermissions().addFamily) {
        return null;
    }
    const name = await askFamilyName({
        titleKey: "familyCreateTitle",
        confirmKey: "save",
        helpKey: showHelp ? "familyCreateHelp" : null,
    });
    if (name === null) {
        return null;
    }
    if (isBusy()) {
        return null;
    }
    state.busy = true;
    try {
        const data = await api(FAMILY_API, {
            method: "POST",
            body: JSON.stringify({ name }),
        });
        replaceFamily(data.family);
        showBanner(t("familyCreated"));
        if (!document.getElementById("family-drawer").hidden) {
            loadFamilyHistory(data.family);
        }
        return data.family;
    } catch (error) {
        showBanner(error.message, true);
        return null;
    } finally {
        state.busy = false;
    }
}

async function toggleFamilyActive(family) {
    if (!catalogPermissions().changeFamily) {
        return;
    }
    if (family.is_active && !window.confirm(t("confirmDeactivateFamily"))) {
        return;
    }
    if (isBusy()) {
        return;
    }
    state.busy = true;
    try {
        const data = await api(`${FAMILY_API}${family.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !family.is_active }),
        });
        replaceFamily(data.family);
        showBanner(t("familySaved"));
        if (state.familyHistoryId === family.id) {
            loadFamilyHistory(data.family);
        }
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
    }
}

function supplierContactLabel(supplier) {
    return supplier.contact_name || supplier.email || supplier.phone || "—";
}

function sortSuppliers() {
    state.suppliers.sort((left, right) =>
        left.name.localeCompare(right.name, currentLang(), { sensitivity: "base" })
    );
}

function replaceSupplier(supplier) {
    const index = state.suppliers.findIndex((item) => item.id === supplier.id);
    if (index === -1) {
        state.suppliers.push(supplier);
    } else {
        state.suppliers[index] = supplier;
    }
    sortSuppliers();
    renderSupplierTable();
}

async function openSupplierDrawer() {
    closeDrawer();
    closeFamilyDrawer();
    document.getElementById("supplier-drawer").hidden = false;
    document.getElementById("supplier-drawer-backdrop").hidden = false;
    try {
        const data = await api(SUPPLIER_API);
        state.suppliers = data.suppliers;
        sortSuppliers();
        renderSupplierTable();
        resetSupplierHistory();
    } catch (error) {
        showBanner(error.message, true);
        renderSupplierTable();
    }
}

function renderSupplierTable() {
    const body = document.getElementById("supplier-table-body");
    if (!body) {
        return;
    }
    body.replaceChildren();
    if (!state.suppliers.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "empty-row";
        cell.textContent = t("emptySuppliers");
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }
    state.suppliers.forEach((supplier) => {
        const row = document.createElement("tr");
        if (!supplier.is_active) {
            row.classList.add("is-inactive");
        }

        const name = document.createElement("td");
        name.textContent = supplier.name;

        const contact = document.createElement("td");
        contact.textContent = supplierContactLabel(supplier);

        const status = document.createElement("td");
        const pill = document.createElement("span");
        pill.className = supplier.is_active ? "pill pill-ok" : "pill pill-muted";
        pill.textContent = supplier.is_active ? t("active") : t("inactive");
        status.appendChild(pill);

        const actions = document.createElement("td");
        actions.className = "row-actions";
        const perms = catalogPermissions();
        if (perms.changeSupplier) {
            const edit = document.createElement("button");
            edit.type = "button";
            edit.className = "btn";
            edit.textContent = t("edit");
            edit.addEventListener("click", () => promptSupplierForm(supplier));
            actions.appendChild(edit);
            const lifecycle = document.createElement("button");
            lifecycle.type = "button";
            lifecycle.className = supplier.is_active ? "btn btn-danger" : "btn";
            lifecycle.textContent = supplier.is_active ? t("deactivate") : t("reactivate");
            lifecycle.addEventListener("click", () => toggleSupplierActive(supplier));
            actions.appendChild(lifecycle);
        }
        const history = document.createElement("button");
        history.type = "button";
        history.className = "btn";
        history.textContent = t("history");
        history.addEventListener("click", () => loadSupplierHistory(supplier));
        actions.appendChild(history);
        const prices = document.createElement("button");
        prices.type = "button";
        prices.className = "btn";
        prices.textContent = t("supplierPrices");
        prices.addEventListener("click", () => openSupplierPrices(supplier));
        actions.appendChild(prices);

        row.append(name, contact, status, actions);
        body.appendChild(row);
    });
}

function supplierFormPayload() {
    return {
        name: document.getElementById("supplier-field-name").value,
        contact_name: document.getElementById("supplier-field-contact").value,
        email: document.getElementById("supplier-field-email").value,
        phone: document.getElementById("supplier-field-phone").value,
        notes: document.getElementById("supplier-field-notes").value,
    };
}

function askSupplierForm(supplier) {
    return new Promise((resolve) => {
        const backdrop = document.getElementById("supplier-form-dialog-backdrop");
        const dialog = document.getElementById("supplier-form-dialog");
        const title = document.getElementById("supplier-form-dialog-title");
        const error = document.getElementById("supplier-form-error");
        const confirmButton = document.getElementById("supplier-form-confirm");
        const cancelButton = document.getElementById("supplier-form-cancel");
        const nameInput = document.getElementById("supplier-field-name");

        title.textContent = t(supplier ? "supplierEditTitle" : "supplierCreateTitle");
        confirmButton.textContent = t("save");
        nameInput.value = supplier ? supplier.name : "";
        document.getElementById("supplier-field-contact").value = supplier ? supplier.contact_name : "";
        document.getElementById("supplier-field-email").value = supplier ? supplier.email : "";
        document.getElementById("supplier-field-phone").value = supplier ? supplier.phone : "";
        document.getElementById("supplier-field-notes").value = supplier ? supplier.notes : "";
        error.hidden = true;
        backdrop.hidden = false;
        dialog.hidden = false;
        nameInput.focus();
        nameInput.select();

        function finish(value) {
            backdrop.hidden = true;
            dialog.hidden = true;
            confirmButton.removeEventListener("click", onConfirm);
            cancelButton.removeEventListener("click", onCancel);
            backdrop.removeEventListener("click", onCancel);
            nameInput.removeEventListener("keydown", onKey);
            resolve(value);
        }

        function onConfirm() {
            const payload = supplierFormPayload();
            if (!payload.name.trim()) {
                error.textContent = t("supplier_name_required");
                error.hidden = false;
                nameInput.focus();
                return;
            }
            finish(payload);
        }

        function onCancel() {
            finish(null);
        }

        function onKey(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                onConfirm();
            }
            if (event.key === "Escape") {
                onCancel();
            }
        }

        confirmButton.addEventListener("click", onConfirm);
        cancelButton.addEventListener("click", onCancel);
        backdrop.addEventListener("click", onCancel);
        nameInput.addEventListener("keydown", onKey);
    });
}

async function promptSupplierForm(supplier) {
    const creating = !supplier;
    if (creating && !catalogPermissions().addSupplier) {
        return null;
    }
    if (!creating && !catalogPermissions().changeSupplier) {
        return null;
    }
    const payload = await askSupplierForm(supplier);
    if (payload === null) {
        return null;
    }
    if (isBusy()) {
        return null;
    }
    state.busy = true;
    try {
        const data = creating
            ? await api(SUPPLIER_API, {
                method: "POST",
                body: JSON.stringify(payload),
            })
            : await api(`${SUPPLIER_API}${supplier.id}/`, {
                method: "PATCH",
                body: JSON.stringify(payload),
            });
        replaceSupplier(data.supplier);
        showBanner(creating ? t("supplierCreated") : t("supplierSaved"));
        if (!document.getElementById("supplier-drawer").hidden) {
            loadSupplierHistory(data.supplier);
        }
        return data.supplier;
    } catch (error) {
        showBanner(error.message, true);
        return null;
    } finally {
        state.busy = false;
    }
}

async function toggleSupplierActive(supplier) {
    if (!catalogPermissions().changeSupplier) {
        return;
    }
    if (supplier.is_active && !window.confirm(t("confirmDeactivateSupplier"))) {
        return;
    }
    if (isBusy()) {
        return;
    }
    state.busy = true;
    try {
        const data = await api(`${SUPPLIER_API}${supplier.id}/`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !supplier.is_active }),
        });
        replaceSupplier(data.supplier);
        showBanner(t("supplierSaved"));
        if (state.supplierHistoryId === supplier.id) {
            loadSupplierHistory(data.supplier);
        }
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
    }
}

async function startNewItem() {
    if (!catalogPermissions().addItem) {
        return;
    }
    const activeId = firstActiveFamilyId();
    if (activeId) {
        await openDrawer(null, activeId);
        return;
    }
    const family = await promptCreateFamily(true);
    if (!family) {
        return;
    }
    await openDrawer(null, family.id);
}

async function createFamilyFromItemForm() {
    if (isBusy()) {
        return;
    }
    const family = await promptCreateFamily(false);
    if (!family) {
        return;
    }
    document.getElementById("field-family").value = String(family.id);
}

function formPayload(isPatch) {
    const payload = {
        family_id: Number(document.getElementById("field-family").value),
        description: document.getElementById("field-description").value,
        unit_of_measure: document.getElementById("field-unit").value,
        reorder_level: document.getElementById("field-reorder").value,
        vat_rate_id: Number(document.getElementById("field-vat-rate").value),
        retail_price: document.getElementById("field-retail-price").value || "0",
        wholesale_price: document.getElementById("field-wholesale-price").value || "0",
        special_price: document.getElementById("field-special-price").value || "0",
        reason: document.getElementById("field-reason").value,
    };
    if (!isPatch) {
        payload.internal_code = document.getElementById("field-internal-code").value;
    } else {
        const itemId = document.getElementById("field-id").value;
        const item = state.items.find((entry) => String(entry.id) === itemId);
        if (canEditInternalCode(false, item)) {
            const internalCode = document.getElementById("field-internal-code").value.trim();
            if (internalCode) {
                payload.internal_code = internalCode;
            }
        }
    }
    return payload;
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

function renderItemSupplierPrices(entries) {
    const list = document.getElementById("item-supplier-prices-list");
    if (!list) {
        return;
    }
    list.replaceChildren();
    if (!entries.length) {
        const item = document.createElement("li");
        item.textContent = t("noSupplierPrices");
        list.appendChild(item);
        return;
    }
    entries.forEach((entry) => {
        const item = document.createElement("li");
        const price = formatCost(entry.cost_price);
        const primary = entry.primary ? ` · ${t("primary")}` : "";
        item.textContent = `${entry.supplier_name} — ${price}${primary}`;
        list.appendChild(item);
    });
}

async function loadItemSupplierPrices(itemId) {
    const requestId = ++itemSupplierPriceRequestId;
    try {
        const data = await api(`${SUPPLIER_PRICE_API}?item_id=${itemId}`);
        if (requestId !== itemSupplierPriceRequestId) {
            return;
        }
        renderItemSupplierPrices(data.supplier_item_prices);
    } catch (error) {
        if (requestId !== itemSupplierPriceRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function fillSupplierPriceItemSelect(selectedId) {
    const select = document.getElementById("supplier-price-item");
    const options = state.items.map((item) => ({
        value: String(item.id),
        label: `${item.internal_code || "—"} — ${item.description}`,
    }));
    fillSelect(select, options, null);
    if (selectedId && [...select.options].some((opt) => opt.value === String(selectedId))) {
        select.value = String(selectedId);
    }
}

function renderSupplierPrices() {
    const body = document.getElementById("supplier-prices-body");
    if (!body) {
        return;
    }
    body.replaceChildren();
    const perms = catalogPermissions();
    if (!state.supplierPrices.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.className = "empty-row";
        cell.textContent = t("noSupplierPrices");
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }
    state.supplierPrices.forEach((price) => {
        const row = document.createElement("tr");

        const code = document.createElement("td");
        code.textContent = price.internal_code || "—";

        const desc = document.createElement("td");
        desc.textContent = price.item_description || "—";

        const cost = document.createElement("td");
        const costInput = document.createElement("input");
        costInput.type = "number";
        costInput.step = "0.01";
        costInput.min = "0";
        costInput.value = price.cost_price ?? "";
        costInput.disabled = !perms.changeSupplierItemPrice;
        costInput.dataset.priceId = String(price.id);
        cost.appendChild(costInput);

        const primaryCell = document.createElement("td");
        const primaryInput = document.createElement("input");
        primaryInput.type = "checkbox";
        primaryInput.checked = Boolean(price.primary);
        primaryInput.disabled = !perms.changeSupplierItemPrice;
        primaryInput.dataset.priceId = String(price.id);
        primaryCell.appendChild(primaryInput);

        const actions = document.createElement("td");
        actions.className = "row-actions";
        if (perms.changeSupplierItemPrice) {
            const saveButton = document.createElement("button");
            saveButton.type = "button";
            saveButton.className = "btn";
            saveButton.textContent = t("save");
            saveButton.addEventListener("click", () => updateSupplierPrice(price, saveButton));
            actions.appendChild(saveButton);
        }

        row.append(code, desc, cost, primaryCell, actions);
        body.appendChild(row);
    });
}

async function updateSupplierPrice(price, button) {
    if (!catalogPermissions().changeSupplierItemPrice) {
        return;
    }
    if (isBusy()) {
        return;
    }
    const costInput = document.querySelector(`input[data-price-id="${price.id}"][type="number"]`);
    const primaryInput = document.querySelector(`input[data-price-id="${price.id}"][type="checkbox"]`);
    const payload = {
        cost_price: costInput ? costInput.value : price.cost_price,
        primary: primaryInput ? primaryInput.checked : price.primary,
    };
    button.disabled = true;
    state.busy = true;
    try {
        const data = await api(`${SUPPLIER_PRICE_API}${price.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
        });
        const index = state.supplierPrices.findIndex((entry) => entry.id === price.id);
        if (index !== -1) {
            state.supplierPrices[index] = data.supplier_item_price;
        }
        renderSupplierPrices();
        showBanner(t("supplierPriceSaved"));
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        button.disabled = false;
    }
}

async function submitSupplierPriceAdd(event) {
    event.preventDefault();
    if (!catalogPermissions().addSupplierItemPrice) {
        return;
    }
    if (isBusy()) {
        return;
    }
    const supplierId = state.supplierPriceSupplierId;
    if (!supplierId) {
        return;
    }
    const itemId = document.getElementById("supplier-price-item").value;
    const costPrice = document.getElementById("supplier-price-cost").value;
    const primary = document.getElementById("supplier-price-primary").checked;
    const addButton = document.getElementById("supplier-price-add");
    addButton.disabled = true;
    state.busy = true;
    try {
        const data = await api(SUPPLIER_PRICE_API, {
            method: "POST",
            body: JSON.stringify({
                supplier_id: supplierId,
                item_id: Number(itemId),
                cost_price: costPrice || "0",
                primary,
            }),
        });
        state.supplierPrices.push(data.supplier_item_price);
        renderSupplierPrices();
        document.getElementById("supplier-price-cost").value = "";
        document.getElementById("supplier-price-primary").checked = false;
        showBanner(t("supplierPriceAdded"));
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        addButton.disabled = false;
    }
}

async function openSupplierPrices(supplier) {
    const requestId = ++supplierPriceRequestId;
    state.supplierPriceSupplierId = supplier.id;
    document.getElementById("supplier-prices-title").textContent = t("supplierPriceDialogTitle", {
        name: supplier.name,
    });
    document.getElementById("supplier-prices-backdrop").hidden = false;
    document.getElementById("supplier-prices-dialog").hidden = false;
    const canAdd = catalogPermissions().addSupplierItemPrice;
    document.getElementById("supplier-price-form").hidden = !canAdd;
    document.getElementById("supplier-price-add").hidden = !canAdd;
    document.getElementById("supplier-price-error").hidden = true;
    document.getElementById("supplier-price-cost").value = "";
    document.getElementById("supplier-price-primary").checked = false;
    fillSupplierPriceItemSelect(null);
    state.supplierPrices = [];
    renderSupplierPrices();
    try {
        const data = await api(`${SUPPLIER_PRICE_API}?supplier_id=${supplier.id}`);
        if (requestId !== supplierPriceRequestId) {
            return;
        }
        state.supplierPrices = data.supplier_item_prices;
        renderSupplierPrices();
    } catch (error) {
        if (requestId !== supplierPriceRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function closeSupplierPrices() {
    supplierPriceRequestId += 1;
    state.supplierPriceSupplierId = null;
    state.supplierPrices = [];
    document.getElementById("supplier-prices-backdrop").hidden = true;
    document.getElementById("supplier-prices-dialog").hidden = true;
}

function formatDateTime(isoString) {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
        return isoString;
    }
    const pad = (value) => String(value).padStart(2, "0");
    return (
        pad(date.getDate()) + "/" +
        pad(date.getMonth() + 1) + "/" +
        date.getFullYear() + " " +
        pad(date.getHours()) + ":" +
        pad(date.getMinutes())
    );
}

function fillHistoryList(list, entries) {
    list.replaceChildren();
    if (!entries.length) {
        const item = document.createElement("li");
        item.textContent = t("noHistory");
        list.appendChild(item);
        return;
    }
    entries.forEach((entry) => {
        const item = document.createElement("li");
        const actionKey = `action${entry.action.charAt(0).toUpperCase()}${entry.action.slice(1)}`;
        const when = formatDateTime(entry.created_at);
        const who = entry.user_email || "—";
        const reason = entry.reason ? ` — ${entry.reason}` : "";
        item.textContent = `${t(actionKey)} · ${who} · ${when}${reason}`;
        list.appendChild(item);
    });
}

async function loadHistory(itemId) {
    const requestId = ++itemHistoryRequestId;
    const list = document.getElementById("history-list");
    try {
        const data = await api(`${API_ROOT}${itemId}/history/`);
        if (requestId !== itemHistoryRequestId) {
            return;
        }
        fillHistoryList(list, data.history);
    } catch (error) {
        if (requestId !== itemHistoryRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function resetFamilyHistory() {
    familyHistoryRequestId += 1;
    state.familyHistoryId = null;
    state.familyHistoryEntries = [];
    const title = document.getElementById("family-history-title");
    const hint = document.getElementById("family-history-hint");
    const list = document.getElementById("family-history-list");
    if (!title || !hint || !list) {
        return;
    }
    title.textContent = t("history");
    hint.hidden = false;
    list.replaceChildren();
}

function showFamilyHistory(family) {
    const title = document.getElementById("family-history-title");
    const hint = document.getElementById("family-history-hint");
    const list = document.getElementById("family-history-list");
    if (!title || !hint || !list) {
        return;
    }
    title.textContent = t("historyFor", { name: family.name });
    hint.hidden = true;
    fillHistoryList(list, state.familyHistoryEntries);
}

async function loadFamilyHistory(family) {
    const requestId = ++familyHistoryRequestId;
    state.familyHistoryId = family.id;
    const title = document.getElementById("family-history-title");
    const hint = document.getElementById("family-history-hint");
    if (title) {
        title.textContent = t("historyFor", { name: family.name });
    }
    if (hint) {
        hint.hidden = true;
    }
    try {
        const data = await api(`${FAMILY_API}${family.id}/history/`);
        if (requestId !== familyHistoryRequestId) {
            return;
        }
        state.familyHistoryEntries = data.history;
        showFamilyHistory(family);
    } catch (error) {
        if (requestId !== familyHistoryRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function resetSupplierHistory() {
    supplierHistoryRequestId += 1;
    state.supplierHistoryId = null;
    state.supplierHistoryEntries = [];
    const title = document.getElementById("supplier-history-title");
    const hint = document.getElementById("supplier-history-hint");
    const list = document.getElementById("supplier-history-list");
    if (!title || !hint || !list) {
        return;
    }
    title.textContent = t("history");
    hint.hidden = false;
    list.replaceChildren();
}

function showSupplierHistory(supplier) {
    const title = document.getElementById("supplier-history-title");
    const hint = document.getElementById("supplier-history-hint");
    const list = document.getElementById("supplier-history-list");
    if (!title || !hint || !list) {
        return;
    }
    title.textContent = t("historyFor", { name: supplier.name });
    hint.hidden = true;
    fillHistoryList(list, state.supplierHistoryEntries);
}

async function loadSupplierHistory(supplier) {
    const requestId = ++supplierHistoryRequestId;
    state.supplierHistoryId = supplier.id;
    const title = document.getElementById("supplier-history-title");
    const hint = document.getElementById("supplier-history-hint");
    if (title) {
        title.textContent = t("historyFor", { name: supplier.name });
    }
    if (hint) {
        hint.hidden = true;
    }
    try {
        const data = await api(`${SUPPLIER_API}${supplier.id}/history/`);
        if (requestId !== supplierHistoryRequestId) {
            return;
        }
        state.supplierHistoryEntries = data.history;
        showSupplierHistory(supplier);
    } catch (error) {
        if (requestId !== supplierHistoryRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function refreshEntityHistoryLabels() {
    if (state.familyHistoryId) {
        const family = state.families.find((item) => item.id === state.familyHistoryId);
        if (family) {
            showFamilyHistory(family);
        } else {
            resetFamilyHistory();
        }
    } else {
        const title = document.getElementById("family-history-title");
        if (title) {
            title.textContent = t("history");
        }
    }
    if (state.supplierHistoryId) {
        const supplier = state.suppliers.find((item) => item.id === state.supplierHistoryId);
        if (supplier) {
            showSupplierHistory(supplier);
        } else {
            resetSupplierHistory();
        }
    } else {
        const title = document.getElementById("supplier-history-title");
        if (title) {
            title.textContent = t("history");
        }
    }
}

async function openDrawer(item, selectFamilyId) {
    closeFamilyDrawer();
    closeSupplierDrawer();
    fillFormLookups();
    document.getElementById("drawer").hidden = false;
    document.getElementById("drawer-backdrop").hidden = false;
    document.getElementById("field-reason").value = "";
    const historyList = document.getElementById("history-list");
    historyList.replaceChildren();

    if (!item) {
        state.editingId = null;
        document.getElementById("field-id").value = "";
        document.getElementById("field-internal-code").value = "";
        document.getElementById("field-description").value = "";
        document.getElementById("field-reorder").value = "0";
        document.getElementById("field-retail-price").value = "0";
        document.getElementById("field-wholesale-price").value = "0";
        document.getElementById("field-special-price").value = "0";
        itemSupplierPriceRequestId += 1;
        renderItemSupplierPrices([]);
        const familyId = selectFamilyId || firstActiveFamilyId();
        if (familyId) {
            document.getElementById("field-family").value = String(familyId);
        }
        if (state.units.length) {
            document.getElementById("field-unit").value = state.units[0].value;
        }
        if (state.vat_rates.length) {
            document.getElementById("field-vat-rate").value = String(state.vat_rates[0].id);
        }
        refreshDrawerLabels();
        return;
    }

    state.editingId = item.id;
    document.getElementById("field-id").value = String(item.id);
    document.getElementById("field-internal-code").value = item.internal_code;
    document.getElementById("field-description").value = item.description;
    document.getElementById("field-family").value = String(item.family.id);
    document.getElementById("field-reorder").value = item.reorder_level;
    document.getElementById("field-retail-price").value = item.retail_price ?? "0";
    document.getElementById("field-wholesale-price").value = item.wholesale_price ?? "0";
    document.getElementById("field-special-price").value = item.special_price ?? "0";
    document.getElementById("field-unit").value = item.unit_of_measure;
    if (item.vat_rate) {
        document.getElementById("field-vat-rate").value = String(item.vat_rate.id);
    }
    refreshDrawerLabels();
    loadItemSupplierPrices(item.id);
    try {
        await loadHistory(item.id);
    } catch (error) {
        showBanner(error.message, true);
    }
}

async function saveItem(event) {
    event.preventDefault();
    const perms = catalogPermissions();
    const itemId = document.getElementById("field-id").value;
    if (itemId ? !perms.changeItem : !perms.addItem) {
        return;
    }
    if (isBusy()) {
        return;
    }
    clearBanner();
    const saveButton = document.getElementById("item-save");
    saveButton.disabled = true;
    state.busy = true;
    const payload = formPayload(Boolean(itemId));
    try {
        let data;
        if (itemId) {
            data = await api(`${API_ROOT}${itemId}/`, {
                method: "PATCH",
                body: JSON.stringify(payload),
            });
            replaceItem(data.item);
            showBanner(t("saved"));
            await loadHistory(data.item.id);
        } else {
            const internalCode = document.getElementById("field-internal-code").value.trim();
            if (!internalCode) {
                showBanner(t("internal_code_required"), true);
                return;
            }
            const retailPrice = Number.parseFloat(
                document.getElementById("field-retail-price").value || "0",
            );
            if (!(retailPrice > 0)) {
                showBanner(t("retail_price_genesis_required"), true);
                return;
            }
            const reason = await askLifecycleReason("genesis");
            if (reason === null) {
                return;
            }
            data = await api(API_ROOT, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            replaceItem(data.item);
            closeDrawer();
            renderTable();
            showBanner(t("activated"));
        }
        renderTable();
        refreshDrawerLabels();
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        saveButton.disabled = false;
    }
}

function lifecycleDialogConfig(mode) {
    if (mode === "genesis") {
        return {
            titleKey: "lifecycleGenesisTitle",
            helpKey: "genesisHelp",
            confirmKey: "genesisConfirm",
            confirmClass: "btn btn-primary",
            errorKey: "reactivate_reason_required",
        };
    }
    if (mode === "activate") {
        return {
            titleKey: "lifecycleActivateTitle",
            helpKey: null,
            confirmKey: "activate",
            confirmClass: "btn btn-primary",
            errorKey: "reactivate_reason_required",
        };
    }
    return {
        titleKey: "lifecycleDeactivateTitle",
        helpKey: null,
        confirmKey: "deactivate",
        confirmClass: "btn btn-danger",
        errorKey: "deactivate_reason_required",
    };
}

function askLifecycleReason(mode) {
    return new Promise((resolve) => {
        const config = lifecycleDialogConfig(mode);
        const backdrop = document.getElementById("lifecycle-dialog-backdrop");
        const dialog = document.getElementById("lifecycle-dialog");
        const title = document.getElementById("lifecycle-dialog-title");
        const help = document.getElementById("lifecycle-dialog-help");
        const presetList = document.getElementById("lifecycle-preset-list");
        const customWrap = document.getElementById("lifecycle-custom-wrap");
        const customInput = document.getElementById("lifecycle-custom-input");
        const error = document.getElementById("lifecycle-reason-error");
        const confirmButton = document.getElementById("lifecycle-confirm");
        const cancelButton = document.getElementById("lifecycle-cancel");
        const presets = LIFECYCLE_PRESETS[mode];

        title.textContent = t(config.titleKey);
        if (config.helpKey) {
            help.textContent = t(config.helpKey);
            help.hidden = false;
        } else {
            help.hidden = true;
        }
        confirmButton.textContent = t(config.confirmKey);
        confirmButton.className = config.confirmClass;
        customInput.value = "";
        error.hidden = true;
        customWrap.hidden = true;

        presetList.replaceChildren();
        presets.forEach((preset, index) => {
            const label = document.createElement("label");
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "lifecycle-preset";
            input.value = preset.value;
            input.checked = index === 0;
            const text = document.createElement("span");
            text.textContent = t(preset.labelKey);
            label.append(input, text);
            presetList.appendChild(label);
        });

        function selectedValue() {
            const selected = presetList.querySelector('input[name="lifecycle-preset"]:checked');
            return selected ? selected.value : "";
        }

        function syncCustomField() {
            customWrap.hidden = selectedValue() !== LIFECYCLE_OTHER;
            if (!customWrap.hidden) {
                customInput.focus();
            }
        }

        function finish(value) {
            backdrop.hidden = true;
            dialog.hidden = true;
            confirmButton.removeEventListener("click", onConfirm);
            cancelButton.removeEventListener("click", onCancel);
            backdrop.removeEventListener("click", onCancel);
            customInput.removeEventListener("keydown", onKey);
            presetList.removeEventListener("change", syncCustomField);
            resolve(value);
        }

        function onConfirm() {
            const value = selectedValue();
            if (!value) {
                error.textContent = t(config.errorKey);
                error.hidden = false;
                return;
            }
            if (value === LIFECYCLE_OTHER) {
                const custom = customInput.value.trim();
                if (!custom) {
                    error.textContent = t(config.errorKey);
                    error.hidden = false;
                    customInput.focus();
                    return;
                }
                finish(custom);
                return;
            }
            finish(value);
        }

        function onCancel() {
            finish(null);
        }

        function onKey(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onConfirm();
            }
            if (event.key === "Escape") {
                onCancel();
            }
        }

        presetList.addEventListener("change", syncCustomField);
        confirmButton.addEventListener("click", onConfirm);
        cancelButton.addEventListener("click", onCancel);
        backdrop.addEventListener("click", onCancel);
        customInput.addEventListener("keydown", onKey);
        backdrop.hidden = false;
        dialog.hidden = false;
        syncCustomField();
        if (customWrap.hidden) {
            confirmButton.focus();
        }
    });
}

async function toggleLifecycle(item) {
    if (!catalogPermissions().changeItem) {
        return;
    }
    clearBanner();
    const reason = item.is_active
        ? await askLifecycleReason("deactivate")
        : await askLifecycleReason("activate");
    if (reason === null) {
        return;
    }
    if (isBusy()) {
        return;
    }
    const path = item.is_active
        ? `${API_ROOT}${item.id}/deactivate/`
        : `${API_ROOT}${item.id}/reactivate/`;
    state.busy = true;
    try {
        const data = await api(path, {
            method: "POST",
            body: JSON.stringify({ reason }),
        });
        replaceItem(data.item);
        showBanner(item.is_active ? t("deactivated") : t("reactivated"));
        renderTable();
        if (!document.getElementById("drawer").hidden && state.editingId === item.id) {
            await openDrawer(data.item);
        }
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
    }
}

async function applyBulk() {
    if (!catalogPermissions().changeItem) {
        return;
    }
    clearBanner();
    const action = document.getElementById("bulk-action").value;
    const ids = [...state.selectedIds].sort((a, b) => a - b);
    if (!action) {
        showBanner(t("chooseAction"), true);
        return;
    }
    if (!ids.length) {
        showBanner(t("selectRows"), true);
        return;
    }
    let reason = "";
    if (action === "deactivate") {
        reason = await askLifecycleReason("deactivate");
    } else {
        reason = await askLifecycleReason("activate");
    }
    if (reason === null) {
        return;
    }
    if (isBusy()) {
        return;
    }
    const bulkButton = document.getElementById("bulk-apply");
    bulkButton.disabled = true;
    state.busy = true;
    try {
        const data = await api(`${API_ROOT}bulk/`, {
            method: "POST",
            body: JSON.stringify({
                action,
                ids,
                reason,
            }),
        });
        data.items.forEach(replaceItem);
        state.selectedIds.clear();
        document.getElementById("bulk-action").value = "";
        showBanner(t("bulkDone"));
        renderTable();
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        bulkButton.disabled = false;
    }
}

async function loadCatalog() {
    const data = await api(API_ROOT);
    applyCatalogPermissions(data.permissions);
    state.items = data.items;
    state.families = data.families;
    state.units = data.units;
    state.vat_rates = data.vat_rates || [];
    fillFilterOptions();
    fillFormLookups();
    renderTable();
    renderFamilyTable();
    const perms = catalogPermissions();
    document.getElementById("new-family").hidden = !perms.addFamily;
    document.getElementById("new-supplier").hidden = !perms.addSupplier;
}

function bindEvents() {
    document.getElementById("language-select").value = currentLang();
    document.getElementById("language-select").addEventListener("change", (event) => {
        setLanguage(event.target.value);
    });
    document.getElementById("theme-toggle").addEventListener("click", () => {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
    ["search-input", "family-filter", "status-filter", "unit-filter"].forEach((id) => {
        document.getElementById(id).addEventListener("input", () => { resetPage(); renderTable(); });
        document.getElementById(id).addEventListener("change", () => { resetPage(); renderTable(); });
    });
    document.getElementById("select-all").addEventListener("change", (event) => {
        const { rows } = currentPageItems();
        if (event.target.checked) {
            rows.forEach((item) => state.selectedIds.add(item.id));
        } else {
            rows.forEach((item) => state.selectedIds.delete(item.id));
        }
        renderTable();
    });
    document.getElementById("items-prev").addEventListener("click", () => goToPage(state.page - 1));
    document.getElementById("items-next").addEventListener("click", () => goToPage(state.page + 1));
    document.getElementById("bulk-apply").addEventListener("click", applyBulk);
    document.getElementById("manage-families").addEventListener("click", () => {
        openFamilyDrawer();
    });
    document.getElementById("manage-suppliers").addEventListener("click", () => {
        openSupplierDrawer();
    });
    document.getElementById("new-item").addEventListener("click", () => startNewItem());
    document.getElementById("new-family").addEventListener("click", () => promptCreateFamily(false));
    document.getElementById("new-family-inline").addEventListener("click", () => createFamilyFromItemForm());
    document.getElementById("family-drawer-close").addEventListener("click", closeFamilyDrawer);
    document.getElementById("family-drawer-backdrop").addEventListener("click", closeFamilyDrawer);
    document.getElementById("new-supplier").addEventListener("click", () => promptSupplierForm(null));
    document.getElementById("supplier-drawer-close").addEventListener("click", closeSupplierDrawer);
    document.getElementById("supplier-drawer-backdrop").addEventListener("click", closeSupplierDrawer);
    document.getElementById("drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
    document.getElementById("item-form").addEventListener("submit", saveItem);
    document.getElementById("supplier-price-form").addEventListener("submit", submitSupplierPriceAdd);
    document.getElementById("supplier-price-cancel").addEventListener("click", closeSupplierPrices);
    document.getElementById("supplier-prices-backdrop").addEventListener("click", closeSupplierPrices);
    document.getElementById("drawer-lifecycle").addEventListener("click", () => {
        const item = state.items.find((item) => item.id === state.editingId);
        if (item) {
            toggleLifecycle(item);
        }
    });
    const sortableHead = document.querySelector(".page .grid thead");
    if (sortableHead) {
        sortableHead.addEventListener("click", (event) => {
            const button = event.target.closest("th[data-sort] .sort-btn");
            if (!button) {
                return;
            }
            event.preventDefault();
            const key = button.closest("th").getAttribute("data-sort");
            toggleSort(key);
            resetPage();
            renderTable();
        });
    }
}

async function init() {
    applyStaticI18n();
    refreshEntityHistoryLabels();
    bindEvents();
    try {
        await loadCatalog();
    } catch (error) {
        showBanner(t("loadFailed"), true);
    }
}

init();
