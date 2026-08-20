const PO_API = "/api/manage/purchase-orders/";
const ITEM_API = "/api/manage/items/";
const SUPPLIER_API = "/api/manage/suppliers/";
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
    purchaseOrders: [],
    suppliers: [],
    items: [],
    statusFilter: "all",
    openId: null,
    openPo: null,
    editingLineId: null,
    busy: false,
};

let poDetailRequestId = 0;
let historyRequestId = 0;

function currentLang() {
    return safeGetStorage(LANG_KEY, "en");
}

function currentTheme() {
    return safeGetStorage(THEME_KEY, "light");
}

function t(key, vars) {
    const dict = PO_I18N[currentLang()] || PO_I18N.en;
    let text = dict[key] || PO_I18N.en[key] || key;
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

function poPermissions() {
    const body = document.body;
    return {
        add: body.dataset.canAddPurchaseorder === "true",
        change: body.dataset.canChangePurchaseorder === "true",
        approve: body.dataset.canApprovePurchaseorder === "true",
    };
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

function formatPercent(value) {
    if (value === null || value === undefined || value === "") {
        return "0%";
    }
    const trimmed = String(value).replace(/\.?0+$/, "");
    return (trimmed === "" || trimmed === "-0" ? "0" : trimmed) + "%";
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
    renderTable();
    if (state.openPo) {
        renderDrawer(state.openPo);
    }
}

function statusLabel(status) {
    return t(`status.${status}`);
}

function statusPillClass(status) {
    switch (status) {
        case "approved":
        case "received":
            return "pill pill-ok";
        case "rejected":
            return "pill pill-danger";
        case "closed":
            return "pill pill-muted";
        case "submitted":
            return "pill pill-warn";
        case "draft":
        default:
            return "pill pill-info";
    }
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

function textTd(value) {
    const td = document.createElement("td");
    td.textContent = value;
    return td;
}

function filteredPurchaseOrders() {
    if (state.statusFilter === "all") {
        return [...state.purchaseOrders];
    }
    return state.purchaseOrders.filter((po) => po.status === state.statusFilter);
}

function replacePurchaseOrder(po) {
    const index = state.purchaseOrders.findIndex((entry) => entry.id === po.id);
    if (index === -1) {
        state.purchaseOrders.push(po);
    } else {
        state.purchaseOrders[index] = po;
    }
}

function renderTable() {
    const body = document.getElementById("po-table-body");
    if (!body) {
        return;
    }
    const rows = filteredPurchaseOrders().sort((left, right) => left.id - right.id);
    body.replaceChildren();

    document.getElementById("result-count").textContent = t("showingCount", {
        shown: rows.length,
        total: state.purchaseOrders.length,
    });

    if (rows.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.className = "empty-row";
        cell.textContent = state.purchaseOrders.length === 0 ? t("empty") : t("noMatch");
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }

    rows.forEach((po) => {
        const row = document.createElement("tr");

        const id = textTd(`#${po.id}`);
        const supplier = textTd(po.supplier_name);

        const status = document.createElement("td");
        const pill = document.createElement("span");
        pill.className = statusPillClass(po.status);
        pill.textContent = statusLabel(po.status);
        status.appendChild(pill);

        const gross = (po.approved_gross !== undefined && po.approved_gross !== null)
            ? po.approved_gross
            : po.total_gross;
        const total = textTd(formatCost(gross));
        const created = textTd(formatDateTime(po.created_at));

        const actions = document.createElement("td");
        actions.className = "row-actions";
        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.className = "btn";
        openButton.textContent = t("open");
        openButton.addEventListener("click", (event) => {
            event.stopPropagation();
            openDrawer(po.id);
        });
        actions.appendChild(openButton);

        row.append(id, supplier, status, total, created, actions);
        row.addEventListener("click", () => openDrawer(po.id));
        body.appendChild(row);
    });
}

function renderDrawer(po) {
    const perms = poPermissions();

    document.getElementById("drawer-title").textContent = t("purchaseOrder", { id: po.id });
    document.getElementById("po-supplier").textContent = po.supplier_name;
    const statusPill = document.getElementById("po-status-pill");
    statusPill.className = statusPillClass(po.status);
    statusPill.textContent = statusLabel(po.status);
    document.getElementById("po-ref").textContent = po.supplier_ref || "—";
    document.getElementById("po-notes").textContent = po.notes || "—";
    document.getElementById("po-created-by").textContent = po.created_by || "—";
    document.getElementById("po-approved-by").textContent = po.approved_by || "—";
    document.getElementById("po-approved-at").textContent = po.approved_at ? formatDateTime(po.approved_at) : "—";
    const hasApproved = po.approved_net !== undefined && po.approved_net !== null;
    document.getElementById("po-net").textContent = formatCost(hasApproved ? po.approved_net : po.total_net);
    document.getElementById("po-vat").textContent = formatCost(hasApproved ? po.approved_vat : (po.total_vat || "0"));
    document.getElementById("po-gross").textContent = formatCost(hasApproved ? po.approved_gross : (po.total_gross || "0"));

    renderLines(po, perms);
    renderStatusActions(po, perms);
}

function renderLines(po, perms) {
    const body = document.getElementById("po-lines-body");
    body.replaceChildren();

    const canEditLines = po.status === "draft" && perms.change;
    document.getElementById("add-line").hidden = !canEditLines;

    if (!po.lines.length) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 10;
        cell.className = "empty-row";
        cell.textContent = t("noLines");
        row.appendChild(cell);
        body.appendChild(row);
        return;
    }

    po.lines.forEach((line) => {
        const row = document.createElement("tr");
        row.appendChild(textTd(line.internal_code || "—"));
        row.appendChild(textTd(line.description));
        row.appendChild(textTd(line.quantity));
        row.appendChild(textTd(formatCost(line.unit_cost)));
        row.appendChild(textTd(formatPercent(line.discount_commercial)));
        row.appendChild(textTd(formatPercent(line.discount_financial)));
        row.appendChild(textTd(formatPercent(line.rappel)));
        row.appendChild(textTd(formatCost(line.line_net)));
        row.appendChild(textTd(formatCost(line.line_total)));

        const actions = document.createElement("td");
        actions.className = "row-actions";
        if (canEditLines) {
            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "btn";
            editButton.textContent = t("edit");
            editButton.addEventListener("click", () => openLineDialog(po, line));
            actions.appendChild(editButton);

            const removeButton = document.createElement("button");
            removeButton.type = "button";
            removeButton.className = "btn btn-danger";
            removeButton.textContent = t("remove");
            removeButton.addEventListener("click", () => removeLine(po.id, line.id, removeButton));
            actions.appendChild(removeButton);
        }
        row.appendChild(actions);
        body.appendChild(row);
    });
}

function renderStatusActions(po, perms) {
    const container = document.getElementById("po-status-actions");
    container.replaceChildren();

    // Receiving goods writes stock via the goods-receipt console.
    if ((po.status === "approved" || po.status === "received") && perms.change) {
        const receiveButton = document.createElement("button");
        receiveButton.type = "button";
        receiveButton.className = "btn btn-primary";
        receiveButton.textContent = t("actionReceiveGoods");
        receiveButton.addEventListener("click", () => {
            window.location.href = `/manage/goods-receipts/?po=${po.id}`;
        });
        container.appendChild(receiveButton);
    }

    let actions = [];
    if (po.status === "draft") {
        if (perms.change) {
            actions = [{ endpoint: "submit/", labelKey: "actionSubmit", successKey: "submitted" }];
        }
    } else if (po.status === "submitted") {
        if (perms.approve) {
            actions.push({ endpoint: "approve/", labelKey: "actionApprove", successKey: "approved" });
        }
        if (perms.change) {
            actions.push({ endpoint: "reject/", labelKey: "actionReject", successKey: "rejected", danger: true });
        }
    } else if (po.status === "received") {
        if (perms.change) {
            actions = [{ endpoint: "close/", labelKey: "actionClose", successKey: "closed", confirmKey: "confirmClose" }];
        }
    }

    actions.forEach((action) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = action.danger ? "btn btn-danger" : "btn btn-primary";
        button.textContent = t(action.labelKey);
        button.addEventListener("click", () => {
            if (action.confirmKey && !window.confirm(t(action.confirmKey))) {
                return;
            }
            performStatusAction(po.id, action.endpoint, action.successKey, button);
        });
        container.appendChild(button);
    });
}

async function performStatusAction(poId, endpoint, successKey, button) {
    if (isBusy()) {
        return;
    }
    button.disabled = true;
    state.busy = true;
    try {
        const data = await api(`${PO_API}${poId}/${endpoint}`, {
            method: "POST",
            body: JSON.stringify({}),
        });
        state.openPo = data.purchase_order;
        replacePurchaseOrder(data.purchase_order);
        renderDrawer(data.purchase_order);
        renderTable();
        loadHistory(poId);
        showBanner(t(successKey));
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        button.disabled = false;
    }
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
        const when = formatDateTime(entry.created_at);
        const who = entry.user_email || "—";
        const reason = entry.reason ? ` — ${entry.reason}` : "";
        item.textContent = `${t(`action.${entry.action}`)} · ${who} · ${when}${reason}`;
        list.appendChild(item);
    });
}

async function loadHistory(poId) {
    const requestId = ++historyRequestId;
    const list = document.getElementById("po-history-list");
    try {
        const data = await api(`${PO_API}${poId}/history/`);
        if (requestId !== historyRequestId) {
            return;
        }
        fillHistoryList(list, data.history);
    } catch (error) {
        if (requestId !== historyRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

async function openDrawer(poId) {
    state.openId = poId;
    document.getElementById("drawer").hidden = false;
    document.getElementById("drawer-backdrop").hidden = false;
    document.getElementById("po-history-list").replaceChildren();
    const requestId = ++poDetailRequestId;
    try {
        const data = await api(`${PO_API}${poId}/`);
        if (requestId !== poDetailRequestId) {
            return;
        }
        state.openPo = data.purchase_order;
        renderDrawer(state.openPo);
        loadHistory(poId);
    } catch (error) {
        if (requestId !== poDetailRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

async function refreshOpenPo() {
    if (!state.openId) {
        return;
    }
    const requestId = ++poDetailRequestId;
    try {
        const data = await api(`${PO_API}${state.openId}/`);
        if (requestId !== poDetailRequestId) {
            return;
        }
        state.openPo = data.purchase_order;
        renderDrawer(state.openPo);
    } catch (error) {
        if (requestId !== poDetailRequestId) {
            return;
        }
        showBanner(error.message, true);
    }
}

function closeDrawer() {
    document.getElementById("drawer").hidden = true;
    document.getElementById("drawer-backdrop").hidden = true;
    poDetailRequestId += 1;
    historyRequestId += 1;
    state.openId = null;
    state.openPo = null;
}

async function ensureItemsLoaded() {
    if (state.items.length) {
        return;
    }
    const data = await api(ITEM_API);
    state.items = data.items;
}

async function ensureSuppliersLoaded() {
    if (state.suppliers.length) {
        return;
    }
    const data = await api(SUPPLIER_API);
    state.suppliers = data.suppliers;
}

function fillSupplierSelect() {
    fillSelect(
        document.getElementById("new-po-supplier"),
        state.suppliers.map((supplier) => ({
            value: String(supplier.id),
            label: supplier.name,
        })),
        t("supplier")
    );
}

function fillItemSelect(selectedId) {
    const select = document.getElementById("line-item");
    fillSelect(
        select,
        state.items.map((item) => ({
            value: String(item.id),
            label: `${item.internal_code || "—"} — ${item.description}`,
        })),
        t("item")
    );
    if (selectedId && [...select.options].some((option) => option.value === String(selectedId))) {
        select.value = String(selectedId);
    }
}

async function openNewPoDialog() {
    if (!poPermissions().add) {
        return;
    }
    document.getElementById("new-po-error").hidden = true;
    document.getElementById("new-po-ref").value = "";
    document.getElementById("new-po-notes").value = "";
    try {
        await ensureSuppliersLoaded();
    } catch (error) {
        showBanner(error.message, true);
        return;
    }
    fillSupplierSelect();
    document.getElementById("new-po-dialog-backdrop").hidden = false;
    document.getElementById("new-po-dialog").hidden = false;
    document.getElementById("new-po-supplier").focus();
}

function closeNewPoDialog() {
    document.getElementById("new-po-dialog-backdrop").hidden = true;
    document.getElementById("new-po-dialog").hidden = true;
}

async function createNewPo() {
    if (!poPermissions().add) {
        return;
    }
    const supplierId = document.getElementById("new-po-supplier").value;
    const error = document.getElementById("new-po-error");
    if (!supplierId) {
        error.textContent = t("supplierRequired");
        error.hidden = false;
        return;
    }
    if (isBusy()) {
        return;
    }
    const confirmButton = document.getElementById("new-po-confirm");
    confirmButton.disabled = true;
    state.busy = true;
    try {
        const data = await api(PO_API, {
            method: "POST",
            body: JSON.stringify({
                supplier_id: Number(supplierId),
                supplier_ref: document.getElementById("new-po-ref").value,
                notes: document.getElementById("new-po-notes").value,
            }),
        });
        const po = data.purchase_order;
        replacePurchaseOrder(po);
        closeNewPoDialog();
        renderTable();
        showBanner(t("poCreated"));
        openDrawer(po.id);
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        confirmButton.disabled = false;
    }
}

function openLineDialog(po, line) {
    if (!po || po.status !== "draft" || !poPermissions().change) {
        return;
    }
    state.editingLineId = line ? line.id : null;
    document.getElementById("line-dialog-title").textContent = t(line ? "lineDialogEdit" : "lineDialogNew");
    document.getElementById("line-confirm").textContent = t("save");
    document.getElementById("line-error").hidden = true;
    document.getElementById("line-quantity").value = line ? line.quantity : "1";
    document.getElementById("line-unit-cost").value = line ? line.unit_cost : "";
    document.getElementById("line-discount-commercial").value = line ? line.discount_commercial : "0";
    document.getElementById("line-discount-financial").value = line ? line.discount_financial : "0";
    document.getElementById("line-rappel").value = line ? line.rappel : "0";
    ensureItemsLoaded()
        .then(() => {
            fillItemSelect(line ? line.item_id : null);
        })
        .catch((error) => showBanner(error.message, true));
    document.getElementById("line-item").disabled = Boolean(line);
    document.getElementById("line-dialog-backdrop").hidden = false;
    document.getElementById("line-dialog").hidden = false;
    document.getElementById("line-quantity").focus();
}

function closeLineDialog() {
    state.editingLineId = null;
    document.getElementById("line-dialog-backdrop").hidden = true;
    document.getElementById("line-dialog").hidden = true;
}

async function onLineConfirm() {
    const po = state.openPo;
    if (!po) {
        return;
    }
    if (isBusy()) {
        return;
    }
    const itemId = document.getElementById("line-item").value;
    const quantity = document.getElementById("line-quantity").value;
    const error = document.getElementById("line-error");
    if (!itemId) {
        error.textContent = t("itemRequired");
        error.hidden = false;
        return;
    }
    if (!quantity || Number(quantity) <= 0) {
        error.textContent = t("quantityRequired");
        error.hidden = false;
        return;
    }
    const confirmButton = document.getElementById("line-confirm");
    confirmButton.disabled = true;
    state.busy = true;
    try {
        const unitCost = document.getElementById("line-unit-cost").value;
        const base = {
            quantity,
            discount_commercial: document.getElementById("line-discount-commercial").value || "0",
            discount_financial: document.getElementById("line-discount-financial").value || "0",
            rappel: document.getElementById("line-rappel").value || "0",
        };
        if (unitCost !== "") {
            base.unit_cost = unitCost;
        }
        let data;
        const lineId = state.editingLineId;
        if (lineId) {
            data = await api(`${PO_API}${po.id}/lines/${lineId}/`, {
                method: "PATCH",
                body: JSON.stringify(base),
            });
        } else {
            base.item_id = Number(itemId);
            data = await api(`${PO_API}${po.id}/lines/`, {
                method: "POST",
                body: JSON.stringify(base),
            });
        }
        closeLineDialog();
        state.openPo = data.purchase_order;
        replacePurchaseOrder(data.purchase_order);
        renderDrawer(data.purchase_order);
        renderTable();
        loadHistory(po.id);
        showBanner(t(lineId ? "lineUpdated" : "lineAdded"));
    } catch (error) {
        const lineError = document.getElementById("line-error");
        lineError.textContent = error.message;
        lineError.hidden = false;
    } finally {
        state.busy = false;
        confirmButton.disabled = false;
    }
}

async function removeLine(poId, lineId, button) {
    const po = state.openPo;
    if (!po || po.status !== "draft" || !poPermissions().change) {
        return;
    }
    if (!window.confirm(t("confirmRemoveLine"))) {
        return;
    }
    if (isBusy()) {
        return;
    }
    button.disabled = true;
    state.busy = true;
    try {
        await api(`${PO_API}${poId}/lines/${lineId}/`, { method: "DELETE" });
        await refreshOpenPo();
        renderTable();
        loadHistory(poId);
        showBanner(t("lineRemoved"));
    } catch (error) {
        showBanner(error.message, true);
    } finally {
        state.busy = false;
        button.disabled = false;
    }
}

function bindEvents() {
    document.getElementById("language-select").value = currentLang();
    document.getElementById("language-select").addEventListener("change", (event) => {
        setLanguage(event.target.value);
    });
    document.getElementById("theme-toggle").addEventListener("click", () => {
        setTheme(currentTheme() === "dark" ? "light" : "dark");
    });
    document.getElementById("status-filter").addEventListener("change", (event) => {
        state.statusFilter = event.target.value;
        renderTable();
    });
    document.getElementById("new-po").addEventListener("click", openNewPoDialog);
    document.getElementById("new-po-confirm").addEventListener("click", createNewPo);
    document.getElementById("new-po-cancel").addEventListener("click", closeNewPoDialog);
    document.getElementById("new-po-dialog-backdrop").addEventListener("click", closeNewPoDialog);
    document.getElementById("drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
    document.getElementById("add-line").addEventListener("click", () => openLineDialog(state.openPo, null));
    document.getElementById("line-confirm").addEventListener("click", onLineConfirm);
    document.getElementById("line-cancel").addEventListener("click", closeLineDialog);
    document.getElementById("line-dialog-backdrop").addEventListener("click", closeLineDialog);
}

async function loadPurchaseOrders() {
    const data = await api(PO_API);
    state.purchaseOrders = data.purchase_orders;
    renderTable();
}

async function init() {
    applyStaticI18n();
    bindEvents();
    try {
        await loadPurchaseOrders();
    } catch (error) {
        showBanner(t("loadFailed"), true);
    }
    Promise.all([ensureItemsLoaded(), ensureSuppliersLoaded()]).catch(() => {
        /* pickers retry on open */
    });
}

init();
