"use strict";

(function () {
    var LANG_KEY = "cc-lang";
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var canReceive = document.body.getAttribute("data-can-receive") === "true";

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
        var dict = WAREHOUSE_INBOUND_I18N[currentLang()] || WAREHOUSE_INBOUND_I18N.en;
        var text = dict[key] !== undefined ? dict[key] : (WAREHOUSE_INBOUND_I18N.en[key] || key);
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
        var dict = WAREHOUSE_INBOUND_I18N[currentLang()] || WAREHOUSE_INBOUND_I18N.en;
        document.querySelectorAll("[data-i18n]").forEach(function (node) {
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
        if (payload && payload.code && WAREHOUSE_INBOUND_I18N.en[payload.code] !== undefined) {
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
            tr.appendChild(el("td", formatDateTime(row.sent_at)));
            tr.appendChild(el("td", row.reason || t("dash")));
            tr.appendChild(el("td", row.total_sent));
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
            tr.appendChild(el("td", formatDateTime(row.sent_at)));
            tr.appendChild(el("td", row.reason || t("dash")));
            tr.appendChild(el("td", row.total_sent));
            tr.appendChild(el("td", row.total_received));
            body.appendChild(tr);
        });
    }

    function renderDetail() {
        var title = document.getElementById("detail-title");
        var meta = document.getElementById("detail-meta");
        var body = document.getElementById("detail-body");
        var empty = document.getElementById("detail-empty");
        var receiveRow = document.getElementById("receive-row");
        if (!title || !body) {
            return;
        }
        body.replaceChildren();
        if (!state.detail) {
            title.textContent = t("detailTitle");
            if (meta) {
                meta.textContent = "";
            }
            if (empty) {
                empty.hidden = false;
                empty.textContent = t("noMatch");
            }
            if (receiveRow) {
                receiveRow.hidden = true;
            }
            return;
        }
        title.textContent = t("detailTitleNum", { id: state.detail.id });
        if (meta) {
            meta.textContent = t("metaLine", {
                branch: state.detail.branch_name || t("dash"),
                by: state.detail.sent_by || t("dash"),
                reason: state.detail.reason || t("dash"),
            });
        }
        if (empty) {
            empty.hidden = true;
        }
        (state.detail.lines || []).forEach(function (line) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", line.internal_code || t("dash")));
            tr.appendChild(el("td", line.description || t("dash")));
            tr.appendChild(el("td", line.quantity_sent));
            var tdQty = document.createElement("td");
            var input = document.createElement("input");
            input.type = "number";
            input.min = "0";
            input.step = "1";
            input.className = "qty";
            input.setAttribute("data-line", String(line.id));
            input.value = String(line.quantity_sent);
            input.disabled = !canReceive;
            tdQty.appendChild(input);
            tr.appendChild(tdQty);
            body.appendChild(tr);
        });
        if (receiveRow) {
            receiveRow.hidden = !canReceive;
        }
    }

    function selectRow(id) {
        state.selectedId = id;
        renderQueue();
        api("/api/manage/incoming-from-branches/" + id + "/").then(function (payload) {
            state.detail = payload.shipment;
            renderDetail();
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function loadQueue() {
        return api("/api/manage/incoming-from-branches/?status=in_transit&page_size=100").then(function (payload) {
            state.queue = payload.shipments || [];
            renderQueue();
        });
    }

    function loadHistory() {
        var path = "/api/manage/incoming-from-branches/?page=" + state.page + "&page_size=" + state.pageSize;
        return api(path).then(function (payload) {
            state.history = payload.shipments || [];
            if (payload.page) {
                state.page = payload.page;
                state.pageSize = payload.page_size;
                state.numPages = payload.num_pages;
            } else {
                state.numPages = state.history.length ? 1 : 0;
            }
            renderHistory();
        });
    }

    function receive() {
        if (!state.detail) {
            return;
        }
        var lines = [];
        var short = false;
        document.querySelectorAll("#detail-body input[data-line]").forEach(function (input) {
            var qty = parseInt(input.value, 10);
            var lineId = parseInt(input.getAttribute("data-line"), 10);
            if (!Number.isFinite(qty) || qty < 0) {
                lines = null;
                return;
            }
            var sent = 0;
            (state.detail.lines || []).forEach(function (line) {
                if (line.id === lineId) {
                    sent = parseInt(line.quantity_sent, 10);
                }
            });
            if (qty < sent) {
                short = true;
            }
            lines.push({ line_id: lineId, quantity_received: qty });
        });
        if (!lines || !lines.length) {
            showBanner(t("needLine"));
            return;
        }
        var reason = document.getElementById("receive-reason");
        if (short && (!reason || !reason.value.trim())) {
            showBanner(t("shortRequired"));
            return;
        }
        api("/api/manage/incoming-from-branches/" + state.detail.id + "/receive/", "POST", {
            reason: reason ? reason.value.trim() : "",
            lines: lines,
        }).then(function () {
            showBanner(t("receivedOk"), true);
            state.selectedId = null;
            state.detail = null;
            if (reason) {
                reason.value = "";
            }
            return Promise.all([loadQueue(), loadHistory()]).then(renderDetail);
        }).catch(function (err) {
            showBanner(err.message);
        });
    }

    function load() {
        Promise.all([loadQueue(), loadHistory()]).then(function () {
            renderDetail();
        }).catch(function () {
            showBanner(t("loadFailed"));
        });
    }

    function bindEvents() {
        var receiveBtn = document.getElementById("receive-btn");
        if (receiveBtn) {
            receiveBtn.addEventListener("click", receive);
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
            renderQueue();
            renderHistory();
            renderDetail();
        });
    }

    applyStaticI18n();
    bindEvents();
    load();
})();
