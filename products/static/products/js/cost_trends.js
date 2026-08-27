const ITEMS_API = "/api/manage/items/";
const THEME_KEY = "cc-theme";
const LANG_KEY = "cc-lang";
const DEFAULT_PERIOD = "last_6_months";
const DEFAULT_ITEM_CODE = "CEM-50";

const PERIODS = [
    "calendar_year",
    "last_6_months",
    "last_3_months",
    "last_30_days",
    "last_7_days",
    "last_1_day",
];

const state = {
    items: [],
    itemId: "",
    period: DEFAULT_PERIOD,
    chart: null,
};

function safeGetStorage(key, fallback) {
    try {
        return localStorage.getItem(key) || fallback;
    } catch (error) {
        return fallback;
    }
}

function currentLang() {
    const raw = safeGetStorage(LANG_KEY, "en");
    return String(raw).toLowerCase().indexOf("pt") === 0 ? "pt-PT" : "en";
}

function t(key) {
    const dict = COST_TRENDS_I18N[currentLang()] || COST_TRENDS_I18N.en;
    return dict[key] || COST_TRENDS_I18N.en[key] || key;
}

function applyI18n() {
    document.title = `${t("title")} — CentCompras`;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = el.getAttribute("data-i18n");
        if (key) {
            el.textContent = t(key);
        }
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (key) {
            el.setAttribute("placeholder", t(key));
        }
    });
    const periodSelect = document.getElementById("cost-period");
    if (periodSelect) {
        periodSelect.querySelectorAll("option").forEach((option) => {
            const key = option.getAttribute("data-i18n");
            if (key) {
                option.textContent = t(key);
            }
        });
    }
}

function showBanner(message, isError) {
    const banner = document.getElementById("banner");
    if (!banner) {
        return;
    }
    if (!message) {
        banner.hidden = true;
        banner.textContent = "";
        return;
    }
    banner.hidden = false;
    banner.textContent = message;
    banner.classList.toggle("is-error", Boolean(isError));
}

function formatMoney(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) {
        return "—";
    }
    return num.toLocaleString(currentLang() === "pt-PT" ? "pt-PT" : "en-GB", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatPct(value) {
    if (value === null || value === undefined || value === "") {
        return "—";
    }
    const num = Number(value);
    if (!Number.isFinite(num)) {
        return "—";
    }
    const sign = num > 0 ? "+" : "";
    return `${sign}${num.toFixed(2)}%`;
}

function itemLabel(item) {
    const code = item.internal_code || "";
    const desc = item.description || "";
    return code ? `${code} — ${desc}` : desc;
}

async function fetchJson(url) {
    const response = await fetch(url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || response.statusText);
    }
    return data;
}

function renderItemOptions() {
    const select = document.getElementById("cost-item");
    if (!select) {
        return;
    }
    const previous = state.itemId;
    select.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t("itemPlaceholder");
    placeholder.disabled = true;
    select.appendChild(placeholder);

    state.items.forEach((item) => {
        const option = document.createElement("option");
        option.value = String(item.id);
        option.textContent = itemLabel(item);
        select.appendChild(option);
    });

    const defaultItem = state.items.find(
        (item) => (item.internal_code || "").toUpperCase() === DEFAULT_ITEM_CODE
    );
    if (previous && state.items.some((item) => String(item.id) === String(previous))) {
        select.value = String(previous);
        state.itemId = String(previous);
    } else if (defaultItem) {
        select.value = String(defaultItem.id);
        state.itemId = String(defaultItem.id);
    } else if (state.items.length) {
        select.value = String(state.items[0].id);
        state.itemId = String(state.items[0].id);
    } else {
        select.value = "";
        state.itemId = "";
    }
}

function updateSummary(summary) {
    const startEl = document.getElementById("summary-start");
    const endEl = document.getElementById("summary-end");
    const pctEl = document.getElementById("summary-pct");
    const noteEl = document.getElementById("primary-switch-note");
    if (!summary) {
        if (startEl) startEl.textContent = "—";
        if (endEl) endEl.textContent = "—";
        if (pctEl) pctEl.textContent = "—";
        if (noteEl) noteEl.hidden = true;
        return;
    }
    if (startEl) startEl.textContent = formatMoney(summary.start_cost);
    if (endEl) endEl.textContent = formatMoney(summary.end_cost);
    if (pctEl) pctEl.textContent = formatPct(summary.change_pct);
    if (noteEl) {
        noteEl.hidden = !summary.primary_switched_in_range;
    }
}

function chartColors() {
    const theme = safeGetStorage(THEME_KEY, "light");
    if (theme === "dark") {
        return {
            line: "#2dd4bf",
            grid: "rgba(148, 163, 184, 0.25)",
            text: "#cbd5e1",
            fill: "rgba(45, 212, 191, 0.12)",
        };
    }
    return {
        line: "#0f766e",
        grid: "rgba(100, 116, 139, 0.2)",
        text: "#475569",
        fill: "rgba(15, 118, 110, 0.08)",
    };
}

function buildStepPoints(points) {
    if (!points.length) {
        return [];
    }
    const steps = [];
    points.forEach((point, index) => {
        const at = new Date(point.at).getTime();
        const cost = Number(point.cost);
        if (index === 0) {
            steps.push({ x: at, y: cost, meta: point });
        } else {
            const prev = points[index - 1];
            steps.push({ x: at, y: Number(prev.cost), meta: prev });
            steps.push({ x: at, y: cost, meta: point });
        }
    });
    return steps;
}

function drawChart(canvas, points) {
    const ctx = canvas.getContext("2d");
    if (!ctx) {
        return;
    }
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!points.length) {
        ctx.fillStyle = chartColors().text;
        ctx.font = "14px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(t("empty"), width / 2, height / 2);
        return;
    }

    const padding = { top: 20, right: 20, bottom: 42, left: 56 };
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;
    const steps = buildStepPoints(points);
    const xs = points.map((p) => new Date(p.at).getTime());
    const ys = points.map((p) => Number(p.cost));
    let minX = Math.min(...xs);
    let maxX = Math.max(...xs);
    let minY = Math.min(...ys);
    let maxY = Math.max(...ys);
    if (minX === maxX) {
        maxX += 3600000;
    }
    if (minY === maxY) {
        minY = minY * 0.95;
        maxY = maxY * 1.05;
    } else {
        const padY = (maxY - minY) * 0.08;
        minY -= padY;
        maxY += padY;
    }

    const xScale = (value) =>
        padding.left + ((value - minX) / (maxX - minX)) * plotW;
    const yScale = (value) =>
        padding.top + plotH - ((value - minY) / (maxY - minY)) * plotH;

    const colors = chartColors();
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i += 1) {
        const yVal = minY + ((maxY - minY) * i) / 4;
        const y = yScale(yVal);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(width - padding.right, y);
        ctx.stroke();
        ctx.fillStyle = colors.text;
        ctx.font = "11px system-ui, sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(formatMoney(yVal), padding.left - 8, y + 4);
    }

    ctx.beginPath();
    steps.forEach((step, index) => {
        const x = xScale(step.x);
        const y = yScale(step.y);
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.lineWidth = 2;
    ctx.strokeStyle = colors.line;
    ctx.stroke();

    ctx.lineTo(xScale(steps[steps.length - 1].x), yScale(minY));
    ctx.lineTo(xScale(steps[0].x), yScale(minY));
    ctx.closePath();
    ctx.fillStyle = colors.fill;
    ctx.fill();

    ctx.fillStyle = colors.text;
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    const tickCount = Math.min(points.length, 4);
    for (let i = 0; i < tickCount; i += 1) {
        const idx = Math.round((i * (points.length - 1)) / Math.max(tickCount - 1, 1));
        const point = points[idx];
        const date = new Date(point.at);
        const label = date.toLocaleDateString(
            currentLang() === "pt-PT" ? "pt-PT" : "en-GB",
            { day: "2-digit", month: "short" }
        );
        ctx.fillText(label, xScale(date.getTime()), height - 14);
    }
}

function resizeChart() {
    const canvas = document.getElementById("cost-chart");
    if (!canvas || !state.chart) {
        return;
    }
    drawChart(canvas, state.chart);
}

async function loadItems() {
    const data = await fetchJson(`${ITEMS_API}?status=active&page_size=200`);
    state.items = data.items || [];
    renderItemOptions();
}

async function loadSeries() {
    if (!state.itemId) {
        updateSummary(null);
        drawChart(document.getElementById("cost-chart"), []);
        return;
    }
    showBanner("");
    try {
        const data = await fetchJson(
            `/api/manage/items/${state.itemId}/cost-series/?period=${encodeURIComponent(state.period)}`
        );
        state.chart = data.points || [];
        updateSummary(data.summary || null);
        drawChart(document.getElementById("cost-chart"), state.chart);
        if (!state.chart.length) {
            showBanner(t("empty"));
        }
    } catch (error) {
        updateSummary(null);
        drawChart(document.getElementById("cost-chart"), []);
        showBanner(error.message || t("loadError"), true);
    }
}

function bindEvents() {
    const periodSelect = document.getElementById("cost-period");
    const itemSelect = document.getElementById("cost-item");
    if (periodSelect) {
        periodSelect.value = state.period;
        periodSelect.addEventListener("change", () => {
            state.period = periodSelect.value;
            loadSeries();
        });
    }
    if (itemSelect) {
        itemSelect.addEventListener("change", () => {
            state.itemId = itemSelect.value;
            loadSeries();
        });
    }
    window.addEventListener("resize", resizeChart);
}

async function init() {
    applyI18n();
    bindEvents();
    try {
        await loadItems();
        await loadSeries();
    } catch (error) {
        showBanner(error.message || t("loadError"), true);
    }
}

document.addEventListener("DOMContentLoaded", init);
