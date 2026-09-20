"use strict";

(function () {
    var LANG_KEY = "cc-lang";
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var canSend = document.body.getAttribute("data-can-send") === "true";

    var state = {
        items: [],
        tickets: [],
        selectedId: null,
        detail: null,
        page: 1,
        pageSize: 50,
        numPages: 0,
        lineSeq: 0,
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
        var dict = BRANCH_SEND_I18N[currentLang()] || BRANCH_SEND_I18N.en;
        var text = dict[key] !== undefined ? dict[key] : (BRANCH_SEND_I18N.en[key] || key);
        if (vars) {
            Object.keys(vars).forEach(function (name) {
                text = text.split("{" + name + "}").join(String(vars[name]));
            });
        }
        return text;
    }

    function applyStaticI18n() {
        document.documentElement.lang = currentLang() === "pt" ? "pt-PT" : "en";
        document.title = t("pageTitle") + " — CentCompras";
        var scope = document.querySelector("main");
        if (!scope) {
            return;
        }
        var dict = BRANCH_SEND_I18N[currentLang()] || BRANCH_SEND_I18N.en;
        scope.querySelectorAll("[data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key && dict[key] !== undefined) {
                node.textContent = t(key);
            }
        });
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

    function isOnline() {
        return typeof BranchOffline === "undefined" || BranchOffline.isOnline();
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

    function showOffline(message) {
        var banner = document.getElementById("offline-banner");
        if (!banner) {
            return;
        }
        banner.textContent = message || "";
        banner.hidden = !message;
    }

    function apiErrorMessage(payload) {
        if (payload && payload.code && BRANCH_SEND_I18N.en[payload.code] !== undefined) {
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

    function stockedItems() {
        return state.items.filter(function (item) {
            return item.is_active !== false && parseInt(item.on_hand, 10) > 0;
        });
    }

    function itemById(itemId) {
        var id = String(itemId);
        for (var i = 0; i < state.items.length; i += 1) {
            if (String(state.items[i].id) === id) {
                return state.items[i];
            }
        }
        return null;
    }

    function itemLabel(item) {
        return (item.internal_code || t("dash")) + " — " + (item.description || "");
    }

    function fillLineSelect(select) {
        if (!select || typeof fillActionSelect !== "function") {
            return;
        }
        fillActionSelect(
            select,
            stockedItems().map(function (item) {
                return { value: String(item.id), label: itemLabel(item) };
            })
        );
    }

    function refreshLineSelects() {
        document.querySelectorAll("#line-body select[data-item]").forEach(function (select) {
            var current = select.value;
            fillLineSelect(select);
            if (current) {
                select.value = current;
            }
            updateOnHandCell(select);
        });
    }

    function updateOnHandCell(select) {
        var row = select.closest("tr");
        if (!row) {
            return;
        }
        var cell = row.querySelector("[data-on-hand]");
        var item = itemById(select.value);
        if (cell) {
            cell.textContent = item ? String(item.on_hand) : t("dash");
        }
        var qty = row.querySelector("input[data-qty]");
        if (qty && item) {
            qty.max = String(item.on_hand);
        }
    }

    function addLine(prefillId) {
        var body = document.getElementById("line-body");
        if (!body) {
            return;
        }
        state.lineSeq += 1;
        var tr = document.createElement("tr");
        tr.dataset.line = String(state.lineSeq);
        var tdItem = document.createElement("td");
        var select = document.createElement("select");
        select.setAttribute("data-item", "1");
        select.setAttribute("aria-label", t("colItem"));
        fillLineSelect(select);
        if (prefillId) {
            select.value = String(prefillId);
        }
        select.addEventListener("change", function () {
            updateOnHandCell(select);
        });
        tdItem.appendChild(select);
        tr.appendChild(tdItem);

        var tdOnHand = document.createElement("td");
        tdOnHand.setAttribute("data-on-hand", "1");
        tdOnHand.textContent = t("dash");
        tr.appendChild(tdOnHand);

        var tdQty = document.createElement("td");
        var qty = document.createElement("input");
        qty.type = "number";
        qty.min = "1";
        qty.step = "1";
        qty.className = "qty";
        qty.setAttribute("data-qty", "1");
        qty.setAttribute("aria-label", t("colQty"));
        tdQty.appendChild(qty);
        tr.appendChild(tdQty);

        var tdRemove = document.createElement("td");
        var remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn";
        remove.textContent = t("removeLine");
        remove.addEventListener("click", function () {
            tr.remove();
        });
        tdRemove.appendChild(remove);
        tr.appendChild(tdRemove);

        body.appendChild(tr);
        updateOnHandCell(select);
    }

    function collectLines() {
        var lines = [];
        document.querySelectorAll("#line-body tr").forEach(function (row) {
            var select = row.querySelector("select[data-item]");
            var qty = row.querySelector("input[data-qty]");
            if (!select || !qty) {
                return;
            }
            if (!select.value && qty.value === "") {
                return;
            }
            lines.push({
                item_id: select.value,
                quantity: qty.value,
            });
        });
        return lines;
    }

    function resetForm() {
        var body = document.getElementById("line-body");
        if (body) {
            body.replaceChildren();
        }
        var reason = document.getElementById("send-reason");
        if (reason) {
            reason.value = "";
        }
        if (canSend) {
            addLine();
        }
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

    function statusLabel(status) {
        return t("status_" + status) || status;
    }

    function renderPagination() {
        var prev = document.getElementById("history-prev");
        var next = document.getElementById("history-next");
        var label = document.getElementById("history-page-label");
        if (!prev || !next || !label) {
            return;
        }
        label.textContent = t("pageOf", { page: state.page, pages: Math.max(state.numPages, 1) });
        prev.disabled = state.page <= 1;
        next.disabled = state.page >= state.numPages;
    }

    function renderHistory() {
        var body = document.getElementById("history-body");
        var empty = document.getElementById("history-empty");
        if (!body) {
            return;
        }
        body.replaceChildren();
        if (empty) {
            empty.hidden = state.tickets.length > 0;
            if (!empty.hidden) {
                empty.textContent = t("empty");
            }
        }
        renderPagination();
        state.tickets.forEach(function (ticket) {
            var tr = document.createElement("tr");
            if (ticket.id === state.selectedId) {
                tr.className = "selected";
            }
            tr.appendChild(el("td", "#" + ticket.id));
            tr.appendChild(el("td", formatDateTime(ticket.sent_at)));
            tr.appendChild(el("td", statusLabel(ticket.status)));
            tr.appendChild(el("td", ticket.sent_by || t("dash")));
            tr.appendChild(el("td", ticket.reason || t("dash")));
            tr.appendChild(el("td", ticket.total_sent));
            tr.addEventListener("click", function () {
                selectTicket(ticket.id);
            });
            body.appendChild(tr);
        });
    }

    function renderDetail() {
        var title = document.getElementById("detail-title");
        var body = document.getElementById("detail-body");
        var empty = document.getElementById("detail-empty");
        var cancelRow = document.getElementById("cancel-row");
        if (!title || !body) {
            return;
        }
        body.replaceChildren();
        if (!state.detail) {
            title.textContent = t("detailTitle");
            if (empty) {
                empty.hidden = false;
                empty.textContent = t("noMatch");
            }
            if (cancelRow) {
                cancelRow.hidden = true;
            }
            return;
        }
        title.textContent = t("detailTitleNum", { id: state.detail.id });
        if (empty) {
            empty.hidden = true;
        }
        (state.detail.lines || []).forEach(function (line) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", line.internal_code || t("dash")));
            tr.appendChild(el("td", line.description || t("dash")));
            tr.appendChild(el("td", line.quantity_sent));
            tr.appendChild(el("td", line.quantity_received));
            body.appendChild(tr);
        });
        if (cancelRow) {
            cancelRow.hidden = !(canSend && state.detail.status === "in_transit");
        }
    }

    function selectTicket(id) {
        state.selectedId = id;
        renderHistory();
        api("/api/branch/send-to-warehouse/" + id + "/").then(function (payload) {
            state.detail = payload.shipment;
            renderDetail();
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function loadStock() {
        return api("/api/branch/stock/").then(function (payload) {
            state.items = payload.items || [];
            refreshLineSelects();
            var hint = document.getElementById("no-stock-hint");
            if (hint) {
                hint.hidden = !canSend || stockedItems().length > 0;
                hint.textContent = t("noStock");
            }
        });
    }

    function loadHistory() {
        var path = "/api/branch/send-to-warehouse/?page=" + state.page + "&page_size=" + state.pageSize;
        return api(path).then(function (payload) {
            state.tickets = payload.shipments || [];
            if (payload.page) {
                state.page = payload.page;
                state.pageSize = payload.page_size;
                state.numPages = payload.num_pages;
            } else {
                state.numPages = state.tickets.length ? 1 : 0;
            }
            renderHistory();
        });
    }

    function send() {
        showBanner("");
        var reason = document.getElementById("send-reason");
        var lines = collectLines();
        if (!lines.length) {
            showBanner(t("needLine"));
            return;
        }
        var missingItem = lines.some(function (line) {
            return !line.item_id;
        });
        if (missingItem) {
            showBanner(t("itemRequired"));
            return;
        }
        var badQty = lines.some(function (line) {
            var qty = parseInt(line.quantity, 10);
            return !Number.isFinite(qty) || qty < 1;
        });
        if (badQty) {
            showBanner(t("qtyRequired"));
            return;
        }
        if (!reason || !reason.value.trim()) {
            showBanner(t("reasonRequired"));
            return;
        }
        var parsed = lines.map(function (line) {
            return {
                item_id: parseInt(line.item_id, 10),
                quantity: parseInt(line.quantity, 10),
            };
        });
        api("/api/branch/send-to-warehouse/", "POST", {
            reason: reason.value.trim(),
            lines: parsed,
        }).then(function (ticket) {
            showBanner(t("sentOk"), true);
            state.selectedId = ticket.id;
            state.detail = ticket;
            resetForm();
            return Promise.all([loadStock(), loadHistory()]).then(function () {
                renderDetail();
            });
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function cancelSend() {
        if (!state.selectedId) {
            return;
        }
        var reason = document.getElementById("cancel-reason");
        if (!reason || !reason.value.trim()) {
            showBanner(t("cancelRequired"));
            return;
        }
        api("/api/branch/send-to-warehouse/" + state.selectedId + "/cancel/", "POST", {
            reason: reason.value.trim(),
        }).then(function (ticket) {
            showBanner(t("cancelledOk"), true);
            state.detail = ticket;
            reason.value = "";
            return Promise.all([loadStock(), loadHistory()]).then(function () {
                renderDetail();
            });
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function syncRoleUi() {
        var panel = document.getElementById("new-panel");
        var hint = document.getElementById("operator-hint");
        if (panel) {
            panel.hidden = !canSend;
        }
        if (hint) {
            hint.hidden = canSend;
            hint.textContent = t("operatorHint");
        }
    }

    function load() {
        syncRoleUi();
        if (!isOnline()) {
            state.items = [];
            state.tickets = [];
            showOffline(t("offlineBanner"));
            var empty = document.getElementById("history-empty");
            if (empty) {
                empty.hidden = false;
                empty.textContent = t("offlineEmpty");
            }
            renderHistory();
            renderDetail();
            return;
        }
        showOffline("");
        Promise.all([loadStock(), loadHistory()]).then(function () {
            if (canSend && !document.querySelector("#line-body tr")) {
                addLine();
            }
            renderDetail();
        }).catch(function () {
            showBanner(t("loadFailed"));
        });
    }

    function bindEvents() {
        var addBtn = document.getElementById("add-line-btn");
        if (addBtn) {
            addBtn.addEventListener("click", function () {
                addLine();
            });
        }
        var sendBtn = document.getElementById("send-btn");
        if (sendBtn) {
            sendBtn.addEventListener("click", send);
        }
        var cancelBtn = document.getElementById("cancel-btn");
        if (cancelBtn) {
            cancelBtn.addEventListener("click", cancelSend);
        }
        var prev = document.getElementById("history-prev");
        if (prev) {
            prev.addEventListener("click", function () {
                if (state.page > 1) {
                    state.page -= 1;
                    loadHistory().catch(function () {
                        showBanner(t("loadFailed"));
                    });
                }
            });
        }
        var next = document.getElementById("history-next");
        if (next) {
            next.addEventListener("click", function () {
                if (state.page < state.numPages) {
                    state.page += 1;
                    loadHistory().catch(function () {
                        showBanner(t("loadFailed"));
                    });
                }
            });
        }
        window.addEventListener("cc-lang-changed", function () {
            applyStaticI18n();
            refreshLineSelects();
            document.querySelectorAll("#line-body button.btn").forEach(function (button) {
                button.textContent = t("removeLine");
            });
            renderHistory();
            renderDetail();
            syncRoleUi();
            var hint = document.getElementById("no-stock-hint");
            if (hint && !hint.hidden) {
                hint.textContent = t("noStock");
            }
        });
    }

    applyStaticI18n();
    bindEvents();
    load();
})();
