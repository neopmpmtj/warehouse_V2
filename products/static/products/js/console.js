const API_ROOT = "/api/manage/items/";
const FAMILY_API = "/api/manage/families/";
const THEME_KEY = "cc-theme";
const LANG_KEY = "cc-lang";

const state = {
    items: [],
    families: [],
    units: [],
    vat_rates: [],
    selectedIds: new Set(),
    editingId: null,
    sortKey: null,
    sortDir: "asc",
    familyHistoryId: null,
    familyHistoryEntries: [],
};

let familyHistoryRequestId = 0;

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
    return localStorage.getItem(LANG_KEY) || "en";
}

function currentTheme() {
    return localStorage.getItem(THEME_KEY) || "light";
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
    localStorage.setItem(THEME_KEY, theme);
    document.documentElement.setAttribute("data-theme", theme);
    applyStaticI18n();
}

function setLanguage(lang) {
    localStorage.setItem(LANG_KEY, lang);
    applyStaticI18n();
    fillFilterOptions();
    fillFormLookups();
    renderTable();
    renderFamilyTable();
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

function renderTable() {
    const body = document.getElementById("item-table-body");
    if (!body) {
        return;
    }
    const rows = sortedItems(filteredItems());
    body.replaceChildren();

    document.getElementById("result-count").textContent = t("showingCount", {
        shown: rows.length,
        total: state.items.length,
    });

    if (rows.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 11;
        cell.className = "empty-row";
        cell.textContent = state.items.length === 0 ? t("empty") : t("noMatch");
        row.appendChild(cell);
        body.appendChild(row);
        updateSortHeaders();
        return;
    }

    rows.forEach((item) => {
        const row = document.createElement("tr");
        if (state.selectedIds.has(item.id)) {
            row.classList.add("is-selected");
        }
        if (!item.is_active) {
            row.classList.add("is-inactive");
        }

        const checkCell = document.createElement("td");
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
        const editButton = document.createElement("button");
        editButton.type = "button";
        editButton.className = "btn";
        editButton.textContent = t("edit");
        editButton.addEventListener("click", (event) => {
            event.stopPropagation();
            openDrawer(item);
        });
        const lifeButton = document.createElement("button");
        lifeButton.type = "button";
        lifeButton.className = item.is_active ? "btn btn-danger" : "btn";
        lifeButton.textContent = item.is_active ? t("deactivate") : t("reactivate");
        lifeButton.addEventListener("click", (event) => {
            event.stopPropagation();
            toggleLifecycle(item);
        });
        actions.append(editButton, lifeButton);

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
    const isNew = !document.getElementById("field-id").value;
    document.getElementById("drawer-title").textContent = isNew ? t("drawerNew") : t("drawerEdit");
    const lifeButton = document.getElementById("drawer-lifecycle");
    if (isNew) {
        lifeButton.hidden = true;
        return;
    }
    const item = state.items.find((item) => String(item.id) === document.getElementById("field-id").value);
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
        const lifecycle = document.createElement("button");
        lifecycle.type = "button";
        lifecycle.className = family.is_active ? "btn btn-danger" : "btn";
        lifecycle.textContent = family.is_active ? t("deactivate") : t("reactivate");
        lifecycle.addEventListener("click", () => toggleFamilyActive(family));
        const history = document.createElement("button");
        history.type = "button";
        history.className = "btn";
        history.textContent = t("history");
        history.addEventListener("click", () => loadFamilyHistory(family));
        actions.append(lifecycle, history);

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
    const name = await askFamilyName({
        titleKey: "familyCreateTitle",
        confirmKey: "save",
        helpKey: showHelp ? "familyCreateHelp" : null,
    });
    if (name === null) {
        return null;
    }
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
    }
}

async function toggleFamilyActive(family) {
    if (family.is_active && !window.confirm(t("confirmDeactivateFamily"))) {
        return;
    }
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
    }
}

async function startNewItem() {
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
    const family = await promptCreateFamily(false);
    if (!family) {
        return;
    }
    document.getElementById("field-family").value = String(family.id);
}

function formPayload() {
    return {
        family_id: Number(document.getElementById("field-family").value),
        internal_code: document.getElementById("field-internal-code").value,
        description: document.getElementById("field-description").value,
        unit_of_measure: document.getElementById("field-unit").value,
        reorder_level: document.getElementById("field-reorder").value,
        vat_rate_id: Number(document.getElementById("field-vat-rate").value),
        reason: document.getElementById("field-reason").value,
    };
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
        const when = new Date(entry.created_at).toLocaleString();
        const who = entry.user_email || "—";
        const reason = entry.reason ? ` — ${entry.reason}` : "";
        item.textContent = `${t(actionKey)} · ${who} · ${when}${reason}`;
        list.appendChild(item);
    });
}

async function loadHistory(itemId) {
    const list = document.getElementById("history-list");
    const data = await api(`${API_ROOT}${itemId}/history/`);
    fillHistoryList(list, data.history);
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
}

async function openDrawer(item, selectFamilyId) {
    closeFamilyDrawer();
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
    document.getElementById("field-unit").value = item.unit_of_measure;
    if (item.vat_rate) {
        document.getElementById("field-vat-rate").value = String(item.vat_rate.id);
    }
    refreshDrawerLabels();
    try {
        await loadHistory(item.id);
    } catch (error) {
        showBanner(error.message, true);
    }
}

async function saveItem(event) {
    event.preventDefault();
    clearBanner();
    const payload = formPayload();
    const productId = document.getElementById("field-id").value;
    try {
        let data;
        if (productId) {
            data = await api(`${API_ROOT}${productId}/`, {
                method: "PATCH",
                body: JSON.stringify(payload),
            });
            replaceItem(data.item);
            showBanner(t("saved"));
            await loadHistory(data.item.id);
        } else {
            data = await api(API_ROOT, {
                method: "POST",
                body: JSON.stringify(payload),
            });
            replaceItem(data.item);
            closeDrawer();
            renderTable();
            const reason = await askLifecycleReason("genesis");
            if (reason === null) {
                showBanner(t("createdInactive"));
                return;
            }
            const activated = await api(`${API_ROOT}${data.item.id}/reactivate/`, {
                method: "POST",
                body: JSON.stringify({ reason }),
            });
            replaceItem(activated.item);
            showBanner(t("activated"));
        }
        renderTable();
        refreshDrawerLabels();
    } catch (error) {
        showBanner(error.message, true);
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
    clearBanner();
    const reason = item.is_active
        ? await askLifecycleReason("deactivate")
        : await askLifecycleReason("activate");
    if (reason === null) {
        return;
    }
    const path = item.is_active
        ? `${API_ROOT}${item.id}/deactivate/`
        : `${API_ROOT}${item.id}/reactivate/`;
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
    }
}

async function applyBulk() {
    clearBanner();
    const action = document.getElementById("bulk-action").value;
    const ids = filteredItems()
        .map((item) => item.id)
        .filter((id) => state.selectedIds.has(id));
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
    }
}

async function loadCatalog() {
    const data = await api(API_ROOT);
    state.items = data.items;
    state.families = data.families;
    state.units = data.units;
    state.vat_rates = data.vat_rates || [];
    fillFilterOptions();
    fillFormLookups();
    renderTable();
    renderFamilyTable();
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
        document.getElementById(id).addEventListener("input", renderTable);
        document.getElementById(id).addEventListener("change", renderTable);
    });
    document.getElementById("select-all").addEventListener("change", (event) => {
        const rows = filteredItems();
        if (event.target.checked) {
            rows.forEach((item) => state.selectedIds.add(item.id));
        } else {
            rows.forEach((item) => state.selectedIds.delete(item.id));
        }
        renderTable();
    });
    document.getElementById("bulk-apply").addEventListener("click", applyBulk);
    document.getElementById("manage-families").addEventListener("click", () => {
        openFamilyDrawer();
    });
    document.getElementById("new-item").addEventListener("click", () => startNewItem());
    document.getElementById("new-family").addEventListener("click", () => promptCreateFamily(false));
    document.getElementById("new-family-inline").addEventListener("click", () => createFamilyFromItemForm());
    document.getElementById("family-drawer-close").addEventListener("click", closeFamilyDrawer);
    document.getElementById("family-drawer-backdrop").addEventListener("click", closeFamilyDrawer);
    document.getElementById("drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
    document.getElementById("item-form").addEventListener("submit", saveItem);
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
