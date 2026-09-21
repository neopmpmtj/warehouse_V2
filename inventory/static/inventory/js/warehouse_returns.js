"use strict";

(function () {
    var LANG_KEY = "cc-lang";
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var canProcess = document.body.getAttribute("data-can-process") === "true";

    var state = {
        queue: [],
        history: [],
        selectedId: null,
        detail: null,
        page: 1,
        pageSize: 50,
        numPages: 0,
    };

    function safeGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function currentLang() {
        var raw = safeGet(LANG_KEY, "pt");
        return String(raw).toLowerCase().indexOf("en") === 0 ? "en" : "pt";
    }

    function t(key, vars) {
        var dict = WAREHOUSE_RETURNS_I18N[currentLang()] || WAREHOUSE_RETURNS_I18N.en;
        var text = dict[key] !== undefined ? dict[key] : (WAREHOUSE_RETURNS_I18N.en[key] || key);
        if (vars) {
            Object.keys(vars).forEach(function (name) {
                text = text.split("{" + name + "}").join(String(vars[name]));
            });
        }
        return text;
    }

    function applyStaticI18n() {
        document.documentElement.lang = currentLang() === "pt" ? "pt-PT" : "en";
        document.title = t("title") + " — CentCompras";
        var dict = WAREHOUSE_RETURNS_I18N[currentLang()] || WAREHOUSE_RETURNS_I18N.en;
        document.querySelectorAll("[data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key && dict[key] !== undefined) {
                node.textContent = t(key);
            }
        });
        setWriteOffQtyVisible(anyWriteOffTicked());
    }

    function el(tag, text, cls) {
        var node = document.createElement(tag);
        if (text != null) {
            node.textContent = text;
        }
        if (cls) {
            node.className = cls;
        }
        return node;
    }

    function showBanner(message, isInfo) {
        var banner = document.getElementById("banner");
        if (!banner) {
            return;
        }
        banner.textContent = message || "";
        banner.hidden = !message;
        banner.classList.toggle("banner-info", Boolean(isInfo));
    }

    function apiErrorMessage(payload) {
        if (payload && payload.code && WAREHOUSE_RETURNS_I18N.en[payload.code] !== undefined) {
            return t(payload.code);
        }
        return (payload && payload.error) || t("requestFailed");
    }

    function api(path, method, body) {
        var opts = {
            method: method || "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json", "X-CSRFToken": CSRF },
        };
        if (body !== undefined) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        return fetch(path, opts).then(function (response) {
            return response.json().then(function (data) {
                if (!response.ok) {
                    throw new Error(apiErrorMessage(data));
                }
                return data;
            });
        });
    }

    function formatDateTime(isoString) {
        var date = new Date(isoString);
        if (Number.isNaN(date.getTime())) {
            return isoString || t("dash");
        }
        var pad = function (value) {
            return String(value).padStart(2, "0");
        };
        return (
            pad(date.getDate()) +
            "/" +
            pad(date.getMonth() + 1) +
            "/" +
            date.getFullYear() +
            " " +
            pad(date.getHours()) +
            ":" +
            pad(date.getMinutes())
        );
    }

    function anyWriteOffTicked() {
        return Boolean(document.querySelector("#detail-body input[data-write-off]:checked"));
    }

    function setWriteOffQtyVisible(visible) {
        document.querySelectorAll(".write-off-qty-col").forEach(function (node) {
            node.hidden = !visible;
        });
    }

    function clampWriteOffQty(input) {
        var max = parseInt(input.max, 10);
        var qty = parseInt(input.value, 10);
        if (!Number.isFinite(max) || max < 1) {
            input.value = "";
            return;
        }
        if (!Number.isFinite(qty) || qty < 1) {
            input.value = "1";
            return;
        }
        if (qty > max) {
            input.value = String(max);
        }
    }

    function syncWriteOffQty(lineId) {
        var box = document.querySelector(
            '#detail-body input[data-write-off="' + lineId + '"]'
        );
        var qty = document.querySelector(
            '#detail-body input[data-write-off-qty="' + lineId + '"]'
        );
        var cell = qty ? qty.parentNode : null;
        var ticked = Boolean(box && box.checked);
        if (qty) {
            qty.disabled = !ticked;
            if (ticked && !qty.value) {
                qty.value = qty.max;
            }
            if (ticked) {
                clampWriteOffQty(qty);
            }
        }
        if (cell) {
            cell.hidden = !ticked;
        }
        setWriteOffQtyVisible(anyWriteOffTicked());
    }

    function renderQueue() {
        var body = document.getElementById("queue-body");
        var empty = document.getElementById("queue-empty");
        if (!body) {
            return;
        }
        body.replaceChildren();
        if (empty) {
            empty.hidden = state.queue.length > 0;
            empty.textContent = t("queueEmpty");
        }
        state.queue.forEach(function (row) {
            var tr = document.createElement("tr");
            if (row.id === state.selectedId) {
                tr.className = "selected";
            }
            tr.appendChild(el("td", "#" + row.id));
            tr.appendChild(el("td", row.branch_name || t("dash")));
            tr.appendChild(el("td", "#" + row.dispatch_id));
            tr.appendChild(el("td", "#" + row.request_id));
            tr.appendChild(el("td", formatDateTime(row.returned_at)));
            tr.addEventListener("click", function () {
                selectRow(row.id);
            });
            body.appendChild(tr);
        });
    }

    function renderHistory() {
        var body = document.getElementById("history-body");
        var empty = document.getElementById("history-empty");
        var label = document.getElementById("history-page-label");
        var prev = document.getElementById("history-prev");
        var next = document.getElementById("history-next");
        if (!body) {
            return;
        }
        body.replaceChildren();
        if (empty) {
            empty.hidden = state.history.length > 0;
            empty.textContent = t("historyEmpty");
        }
        if (label) {
            label.textContent = t("pageOf", { page: state.page, pages: Math.max(state.numPages, 1) });
        }
        if (prev) {
            prev.disabled = state.page <= 1;
        }
        if (next) {
            next.disabled = state.page >= state.numPages;
        }
        state.history.forEach(function (row) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", "#" + row.id));
            tr.appendChild(el("td", row.branch_name || t("dash")));
            tr.appendChild(el("td", t("status_" + row.status) || row.status));
            tr.appendChild(el("td", "#" + row.dispatch_id));
            tr.appendChild(el("td", formatDateTime(row.returned_at)));
            tr.appendChild(el("td", row.total_returned));
            tr.appendChild(el("td", row.total_restocked));
            tr.appendChild(el("td", row.total_written_off));
            body.appendChild(tr);
        });
    }

    function renderDetail() {
        var body = document.getElementById("detail-body");
        var empty = document.getElementById("detail-empty");
        var title = document.getElementById("detail-title");
        var meta = document.getElementById("detail-meta");
        var row = document.getElementById("process-row");
        body.replaceChildren();
        if (!state.detail) {
            title.textContent = t("detailTitle");
            meta.textContent = "";
            empty.hidden = false;
            row.hidden = true;
            setWriteOffQtyVisible(false);
            return;
        }
        empty.hidden = true;
        title.textContent = t("detailTitleNum", { id: state.detail.id });
        meta.textContent = t("metaLine", {
            branch: state.detail.branch_name || t("dash"),
            request: state.detail.request_id,
            dispatch: state.detail.dispatch_id,
        });
        (state.detail.lines || []).forEach(function (line) {
            var remaining = parseInt(line.remaining, 10);
            var tr = document.createElement("tr");
            tr.appendChild(el("td", line.internal_code || t("dash")));
            tr.appendChild(el("td", line.description || ""));
            tr.appendChild(el("td", String(line.quantity_returned)));
            var tdBox = document.createElement("td");
            var box = document.createElement("input");
            box.type = "checkbox";
            box.dataset.writeOff = String(line.line_id);
            box.disabled = !canProcess || remaining <= 0;
            box.addEventListener("change", function () {
                syncWriteOffQty(line.line_id);
            });
            tdBox.appendChild(box);
            tr.appendChild(tdBox);
            var tdQty = document.createElement("td");
            tdQty.className = "write-off-qty-col";
            tdQty.hidden = true;
            var qty = document.createElement("input");
            qty.type = "number";
            qty.step = "1";
            qty.min = "1";
            qty.max = String(Math.max(remaining, 1));
            qty.className = "qty";
            qty.dataset.writeOffQty = String(line.line_id);
            qty.disabled = true;
            qty.value = String(Math.max(remaining, 1));
            qty.addEventListener("input", function () { clampWriteOffQty(qty); });
            qty.addEventListener("change", function () { clampWriteOffQty(qty); });
            tdQty.appendChild(qty);
            tr.appendChild(tdQty);
            body.appendChild(tr);
        });
        row.hidden = !canProcess;
        setWriteOffQtyVisible(false);
    }

    function selectRow(id) {
        state.selectedId = id;
        renderQueue();
        api("/api/manage/returned-dispatches/" + id + "/").then(function (payload) {
            state.detail = payload.dispatch_return;
            renderDetail();
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function loadQueue() {
        return api("/api/manage/returned-dispatches/?status=in_transit&page_size=100").then(function (payload) {
            state.queue = payload.dispatch_returns || [];
            renderQueue();
        });
    }

    function loadHistory() {
        var path = "/api/manage/returned-dispatches/?page=" + state.page + "&page_size=" + state.pageSize;
        return api(path).then(function (payload) {
            state.history = payload.dispatch_returns || [];
            state.numPages = payload.num_pages || 0;
            renderHistory();
        });
    }

    function processReturn() {
        if (!state.detail || !canProcess) {
            return;
        }
        var lines = [];
        var hasWriteOff = false;
        (state.detail.lines || []).forEach(function (line) {
            var box = document.querySelector(
                '#detail-body input[data-write-off="' + line.line_id + '"]'
            );
            var writeOff = Boolean(box && box.checked);
            var row = { line_id: line.line_id, write_off: writeOff };
            if (writeOff) {
                hasWriteOff = true;
                var qty = document.querySelector(
                    '#detail-body input[data-write-off-qty="' + line.line_id + '"]'
                );
                if (qty) {
                    clampWriteOffQty(qty);
                    row.write_off_qty = parseInt(qty.value, 10);
                }
            }
            lines.push(row);
        });
        var reason = document.getElementById("process-reason").value;
        if (hasWriteOff && !String(reason).trim()) {
            showBanner(t("dispatch_write_off_reason_required"));
            return;
        }
        api("/api/manage/returned-dispatches/" + state.selectedId + "/process/", "POST", {
            lines: lines,
            reason: reason,
        }).then(function () {
            showBanner(t("processedOk"), true);
            state.selectedId = null;
            state.detail = null;
            document.getElementById("process-reason").value = "";
            renderDetail();
            return Promise.all([loadQueue(), loadHistory()]);
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    document.getElementById("restock-btn").addEventListener("click", processReturn);
    document.getElementById("history-prev").addEventListener("click", function () {
        if (state.page > 1) {
            state.page -= 1;
            loadHistory().catch(function (err) { showBanner(err.message); });
        }
    });
    document.getElementById("history-next").addEventListener("click", function () {
        if (state.page < state.numPages) {
            state.page += 1;
            loadHistory().catch(function (err) { showBanner(err.message); });
        }
    });

    applyStaticI18n();
    Promise.all([loadQueue(), loadHistory()]).catch(function (err) {
        showBanner(err.message || t("loadFailed"));
    });
    window.addEventListener("cc-lang-changed", function () {
        applyStaticI18n();
        renderQueue();
        renderHistory();
        renderDetail();
    });
})();
