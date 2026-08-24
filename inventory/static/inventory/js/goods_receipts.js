const GR_API = "/api/manage/goods-receipts/";
const PO_API = "/api/manage/purchase-orders/";
const ITEM_API = "/api/manage/items/";
const MOVEMENTS_API = "/api/manage/stock-movements/";
const ADJUST_API = "/api/manage/stock-adjustments/";
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
    receipts: [],
    movements: [],
    items: [],
    purchaseOrders: [],
    receiptSummary: [],
    receiptsPage: 1,
    receiptsPageSize: 50,
    receiptsTotal: 0,
    receiptsNumPages: 0,
    movementsPage: 1,
    movementsPageSize: 50,
    movementsTotal: 0,
    movementsNumPages: 0,
    busy: false,
};

function currentLang() {
    return safeGetStorage(LANG_KEY, "en");
}

function currentTheme() {
    return safeGetStorage(THEME_KEY, "light");
}

function t(key, vars) {
    const dict = GR_I18N[currentLang()] || GR_I18N.en;
    let text = dict[key] || GR_I18N.en[key] || key;
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

function permissions() {
    const body = document.body;
    return {
        add: body.dataset.canAddGoodsreceipt === "true",
        adjust: body.dataset.canAdjustStock === "true",
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

function formatMovementQty(quantity) {
    const value = formatQty(quantity);
    return String(quantity).startsWith("-") ? value : "+" + value;
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
    renderReceipts();
    renderMovements();
    const summary = state.receiptSummary;
    if (summary.length) {
        renderReceiptLines(summary);
    }
}

function movementTypeLabel(type) {
    return t(`movement_type.${type}`);
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

function renderPagination(prefix, page, numPages) {
    const prev = document.getElementById(`${prefix}-prev`);
    const next = document.getElementById(`${prefix}-next`);
    const label = document.getElementById(`${prefix}-page-label`);
    if (!prev || !next || !label) {
        return;
    }
    label.textContent = t("pageOf", { page, pages: Math.max(numPages, 1) });
    prev.disabled = page <= 1;
    next.disabled = page >= numPages;
}

async function goReceiptsPage(page) {
    if (page < 1 || (state.receiptsNumPages > 0 && page > state.receiptsNumPages)) {
        return;
    }
    state.receiptsPage = page;
    try {
        await loadReceipts();
    } catch (error) {
        showBanner(error.message, true);
    }
}

async function goMovementsPage(page) {
    if (page < 1 || (state.movementsNumPages > 0 && page > state.movementsNumPages)) {
        return;
    }
    state.movementsPage = page;
    try {
        await loadMovements();
    } catch (error) {
        showBanner(error.message, true);
    }
}

/* ------------------------------- receipts ------------------------------ */

async function loadReceipts() {
    const params = new URLSearchParams({
        page: String(state.receiptsPage),
        page_size: String(state.receiptsPageSize),
    });
    const data = await api(`${GR_API}?${params.toString()}`);
    state.receipts = data.goods_receipts;
    state.receiptsTotal = data.total || 0;
    state.receiptsNumPages = data.num_pages || 0;
    renderReceipts();
}

function renderReceipts() {
    const body = document.getElementById("receipts-body");
    body.replaceChildren();
    document.getElementById("receipts-empty").hidden = state.receipts.length > 0;
    renderPagination("receipts", state.receiptsPage, state.receiptsNumPages);

    state.receipts.forEach((receipt) => {
        const row = document.createElement("tr");
        row.appendChild(textTd(`#${receipt.id}`));
        row.appendChild(textTd(`#${receipt.purchase_order_id}`));
        row.appendChild(textTd(receipt.supplier_name));
        row.appendChild(textTd(receipt.received_by || "—"));
        row.appendChild(textTd(formatDateTime(receipt.received_at)));
        row.appendChild(textTd(receipt.reference || "—"));
        row.appendChild(textTd(formatQty(receipt.total_received)));
        body.appendChild(row);
    });
}

/* ------------------------------ movements ------------------------------ */

async function loadMovements() {
    const itemId = document.getElementById("movement-item-filter").value;
    const params = new URLSearchParams({
        page: String(state.movementsPage),
        page_size: String(state.movementsPageSize),
    });
    if (itemId) {
        params.set("item_id", itemId);
    }
    const data = await api(`${MOVEMENTS_API}?${params.toString()}`);
    state.movements = data.stock_movements;
    state.movementsTotal = data.total || 0;
    state.movementsNumPages = data.num_pages || 0;
    renderMovements();
}

function renderMovements() {
    const body = document.getElementById("movements-body");
    body.replaceChildren();
    document.getElementById("movements-empty").hidden = state.movements.length > 0;
    renderPagination("movements", state.movementsPage, state.movementsNumPages);

    state.movements.forEach((movement) => {
        const row = document.createElement("tr");
        row.appendChild(textTd(`${movement.internal_code || "—"} — ${movement.description}`));
        row.appendChild(textTd(movementTypeLabel(movement.movement_type)));
        row.appendChild(textTd(formatMovementQty(movement.quantity)));
        row.appendChild(textTd(movement.reference || "—"));
        row.appendChild(textTd(movement.reason || "—"));
        row.appendChild(textTd(movement.created_by || "—"));
        row.appendChild(textTd(formatDateTime(movement.created_at)));
        body.appendChild(row);
    });
}

async function loadItems() {
    if (state.items.length) {
        return;
    }
    const data = await api(ITEM_API);
    state.items = data.items;
}

function fillItemFilter() {
    const select = document.getElementById("movement-item-filter");
    fillSelect(
        select,
        [
            { value: "", label: t("allItems") },
            ...state.items.map((item) => ({
                value: String(item.id),
                label: `${item.internal_code || "—"} — ${item.description}`,
            })),
        ]
    );
    select.value = "";
}

/* ---------------------------- receipt dialog --------------------------- */

async function loadReceivablePurchaseOrders() {
    const data = await api(PO_API);
    state.purchaseOrders = data.purchase_orders.filter(
        (po) => po.status === "approved" || po.status === "received"
    );
}

function fillReceivablePoSelect() {
    const select = document.getElementById("receipt-po");
    fillSelect(
        select,
        state.purchaseOrders.map((po) => ({
            value: String(po.id),
            label: `#${po.id} — ${po.supplier_name}`,
        })),
        t("choosePo")
    );
}

async function onReceiptPoChange() {
    const poId = document.getElementById("receipt-po").value;
    const container = document.getElementById("receipt-lines");
    container.replaceChildren();
    if (!poId) {
        return;
    }
    try {
        const data = await api(`${PO_API}${poId}/receipt-summary/`);
        state.receiptSummary = data.lines;
        renderReceiptLines(data.lines);
    } catch (error) {
        showBanner(error.message, true);
    }
}

function renderReceiptLines(lines) {
    const container = document.getElementById("receipt-lines");
    container.replaceChildren();
    const receivable = lines.filter((line) => Number(line.remaining) > 0);

    if (!receivable.length) {
        const note = document.createElement("p");
        note.className = "drawer-help";
        note.textContent = t("noReceivableLines");
        container.appendChild(note);
        return;
    }

    const table = document.createElement("table");
    table.className = "grid";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    ["lineItem", "lineOrdered", "lineReceived", "lineRemaining", "lineToReceive"].forEach((key) => {
        const th = document.createElement("th");
        th.textContent = t(key);
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    receivable.forEach((line) => {
        const row = document.createElement("tr");
        row.appendChild(textTd(`${line.internal_code || "—"} — ${line.description}`));
        row.appendChild(textTd(formatQty(line.quantity)));
        row.appendChild(textTd(formatQty(line.received)));
        row.appendChild(textTd(formatQty(line.remaining)));

        const td = document.createElement("td");
        const input = document.createElement("input");
        input.type = "number";
        input.step = "0.001";
        input.min = "0";
        input.max = line.remaining;
        input.value = formatQty(line.remaining);
        input.dataset.lineId = String(line.line_id);
        input.className = "receipt-qty-input";
        td.appendChild(input);
        row.appendChild(td);

        tbody.appendChild(row);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

async function openReceiptDialog(preferredPoId) {
    if (!permissions().add) {
        return;
    }
    document.getElementById("receipt-error").hidden = true;
    document.getElementById("receipt-reference").value = "";
    document.getElementById("receipt-notes").value = "";
    document.getElementById("receipt-lines").replaceChildren();
    try {
        await loadReceivablePurchaseOrders();
    } catch (error) {
        showBanner(error.message, true);
        return;
    }
    fillReceivablePoSelect();
    const select = document.getElementById("receipt-po");
    if (preferredPoId && [...select.options].some((option) => option.value === String(preferredPoId))) {
        select.value = String(preferredPoId);
    } else {
        select.value = "";
    }
    state.receiptSummary = [];
    document.getElementById("receipt-dialog-backdrop").hidden = false;
    document.getElementById("receipt-dialog").hidden = false;
    if (select.value) {
        onReceiptPoChange();
        document.getElementById("receipt-reference").focus();
    } else {
        document.getElementById("receipt-po").focus();
    }
}

function closeReceiptDialog() {
    document.getElementById("receipt-dialog-backdrop").hidden = true;
    document.getElementById("receipt-dialog").hidden = true;
    state.receiptSummary = [];
}

async function submitReceipt() {
    const poId = document.getElementById("receipt-po").value;
    const error = document.getElementById("receipt-error");
    if (!poId) {
        error.textContent = t("poRequired");
        error.hidden = false;
        return;
    }
    const lines = [];
    document.querySelectorAll(".receipt-qty-input").forEach((input) => {
        const qty = Number(input.value);
        if (qty > 0) {
            lines.push({
                line_id: Number(input.dataset.lineId),
                quantity_received: String(qty),
            });
        }
    });
    if (!lines.length) {
        error.textContent = t("quantityRequired");
        error.hidden = false;
        return;
    }
    if (isBusy()) {
        return;
    }
    const confirmButton = document.getElementById("receipt-confirm");
    confirmButton.disabled = true;
    state.busy = true;
    try {
        await api(GR_API, {
            method: "POST",
            body: JSON.stringify({
                purchase_order_id: Number(poId),
                reference: document.getElementById("receipt-reference").value,
                notes: document.getElementById("receipt-notes").value,
                lines,
            }),
        });
        closeReceiptDialog();
        await Promise.all([loadReceipts(), loadMovements()]);
        showBanner(t("receiptCreated"));
    } catch (requestError) {
        error.textContent = requestError.message;
        error.hidden = false;
    } finally {
        state.busy = false;
        confirmButton.disabled = false;
    }
}

/* ----------------------------- adjust dialog --------------------------- */

async function openAdjustDialog() {
    if (!permissions().adjust) {
        return;
    }
    document.getElementById("adjust-error").hidden = true;
    document.getElementById("adjust-quantity").value = "";
    document.getElementById("adjust-reason").value = "";
    try {
        await loadItems();
    } catch (error) {
        showBanner(error.message, true);
        return;
    }
    fillItemFilter();
    fillSelect(
        document.getElementById("adjust-item"),
        state.items.map((item) => ({
            value: String(item.id),
            label: `${item.internal_code || "—"} — ${item.description}`,
        })),
        t("chooseItem")
    );
    document.getElementById("adjust-dialog-backdrop").hidden = false;
    document.getElementById("adjust-dialog").hidden = false;
    document.getElementById("adjust-item").focus();
}

function closeAdjustDialog() {
    document.getElementById("adjust-dialog-backdrop").hidden = true;
    document.getElementById("adjust-dialog").hidden = true;
}

async function submitAdjustment() {
    const itemId = document.getElementById("adjust-item").value;
    const quantity = document.getElementById("adjust-quantity").value;
    const error = document.getElementById("adjust-error");
    if (!itemId) {
        error.textContent = t("itemRequired");
        error.hidden = false;
        return;
    }
    if (quantity === "" || Number(quantity) === 0) {
        error.textContent = t("adjustQuantityRequired");
        error.hidden = false;
        return;
    }
    if (isBusy()) {
        return;
    }
    const confirmButton = document.getElementById("adjust-confirm");
    confirmButton.disabled = true;
    state.busy = true;
    try {
        await api(ADJUST_API, {
            method: "POST",
            body: JSON.stringify({
                item_id: Number(itemId),
                quantity,
                reason: document.getElementById("adjust-reason").value,
            }),
        });
        closeAdjustDialog();
        await loadMovements();
        showBanner(t("adjustmentSaved"));
    } catch (requestError) {
        error.textContent = requestError.message;
        error.hidden = false;
    } finally {
        state.busy = false;
        confirmButton.disabled = false;
    }
}

/* -------------------------------- events ------------------------------ */

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

    document.getElementById("movement-item-filter").addEventListener("change", () => {
        state.movementsPage = 1;
        loadMovements().catch((error) => showBanner(error.message, true));
    });
    document.getElementById("receipts-prev").addEventListener("click", () => goReceiptsPage(state.receiptsPage - 1));
    document.getElementById("receipts-next").addEventListener("click", () => goReceiptsPage(state.receiptsPage + 1));
    document.getElementById("movements-prev").addEventListener("click", () => goMovementsPage(state.movementsPage - 1));
    document.getElementById("movements-next").addEventListener("click", () => goMovementsPage(state.movementsPage + 1));

    document.getElementById("new-receipt").addEventListener("click", () => openReceiptDialog());
    document.getElementById("receipt-po").addEventListener("change", onReceiptPoChange);
    document.getElementById("receipt-confirm").addEventListener("click", submitReceipt);
    document.getElementById("receipt-cancel").addEventListener("click", closeReceiptDialog);
    document.getElementById("receipt-dialog-backdrop").addEventListener("click", closeReceiptDialog);

    document.getElementById("adjust-stock").addEventListener("click", openAdjustDialog);
    document.getElementById("adjust-confirm").addEventListener("click", submitAdjustment);
    document.getElementById("adjust-cancel").addEventListener("click", closeAdjustDialog);
    document.getElementById("adjust-dialog-backdrop").addEventListener("click", closeAdjustDialog);
}

async function init() {
    applyStaticI18n();
    bindEvents();

    document.getElementById("new-receipt").hidden = !permissions().add;
    document.getElementById("adjust-stock").hidden = !permissions().adjust;

    try {
        await Promise.all([loadReceipts(), loadMovements(), loadItems()]);
    } catch (error) {
        showBanner(error.message, true);
    }
    fillItemFilter();

    const preferredPo = new URLSearchParams(window.location.search).get("po");
    if (preferredPo && permissions().add) {
        openReceiptDialog(Number(preferredPo));
    }
}

init();
