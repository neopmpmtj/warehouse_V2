"use strict";

(function () {
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var CAN_APPROVE = document.body.getAttribute("data-can-approve") === "true";
    var LANG_KEY = "cc-lang";
    var STATUS_KEYS = {
        draft: "statusDraft",
        submitted: "statusSubmitted",
        approved: "statusApproved",
        rejected: "statusRejected",
        fulfilling: "statusFulfilling",
        shipped: "statusShipped",
        received: "statusReceived",
        closed: "statusClosed",
        cancelled: "statusCancelled",
    };
    var state = { selectedId: null, selectedClientUuid: null, requests: [], pending: [], items: [] };
    var showSellingPrices = false;
    var lineHead = document.getElementById("line-head");

    var requestBody = document.getElementById("request-body");
    var lineBody = document.getElementById("line-body");
    var lineForm = document.getElementById("line-form");
    var lineItem = document.getElementById("line-item");
    var actions = document.getElementById("actions");
    var banner = document.getElementById("banner");
    var detailTitle = document.getElementById("detail-title");
    var detailMeta = document.getElementById("detail-meta");
    var detailTotals = document.getElementById("detail-totals");
    var newRequestBtn = document.getElementById("new-request");

    function safeGetStorage(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function currentLang() {
        var raw = safeGetStorage(LANG_KEY, "pt");
        return String(raw).toLowerCase().indexOf("en") === 0 ? "en" : "pt";
    }

    function t(key, vars) {
        var dict = BRANCH_REQUESTS_I18N[currentLang()] || BRANCH_REQUESTS_I18N.en;
        var text = dict[key] || BRANCH_REQUESTS_I18N.en[key] || key;
        if (vars) {
            Object.keys(vars).forEach(function (name) {
                text = text.split("{" + name + "}").join(String(vars[name]));
            });
        }
        return text;
    }

    function dateLocale() {
        return currentLang() === "pt" ? "pt-PT" : "en-GB";
    }

    function statusLabel(status) {
        var key = STATUS_KEYS[status];
        return key ? t(key) : status;
    }

    function applyStaticI18n() {
        var lang = currentLang();
        document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
        document.title = t("pageTitle") + " — CentCompras";
        document.querySelectorAll("main [data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key) {
                node.textContent = t(key);
            }
        });
        document.querySelectorAll("main [data-i18n-placeholder]").forEach(function (node) {
            node.setAttribute("placeholder", t(node.getAttribute("data-i18n-placeholder")));
        });
    }

    function applyCommercialMode(data) {
        if (data && typeof data.show_selling_prices === "boolean") {
            showSellingPrices = data.show_selling_prices;
        }
    }

    function headerCell(text) {
        var th = document.createElement("th");
        th.textContent = text;
        return th;
    }

    function renderLineHead() {
        if (!lineHead) {
            return;
        }
        lineHead.textContent = "";
        lineHead.appendChild(headerCell(t("colCode")));
        lineHead.appendChild(headerCell(t("colDescription")));
        lineHead.appendChild(headerCell(t("colQty")));
        if (showSellingPrices) {
            lineHead.appendChild(headerCell(t("colUnitPrice")));
        }
        lineHead.appendChild(headerCell(""));
    }

    function el(tag, text, className) {
        var node = document.createElement(tag);
        if (text != null) {
            node.textContent = text;
        }
        if (className) {
            node.className = className;
        }
        return node;
    }

    function showError(msg) {
        banner.textContent = msg || t("requestFailed");
        banner.hidden = false;
    }

    function clearError() {
        banner.hidden = true;
    }

    function varsFromEnglishError(code, errorText) {
        var template = BRANCH_REQUESTS_I18N.en[code];
        if (!template || !errorText) {
            return null;
        }
        var names = [];
        var escaped = template.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        var pattern = escaped.replace(/\\\{([A-Za-z0-9_]+)\\\}/g, function (_, name) {
            names.push(name);
            return "(.+?)";
        });
        if (!names.length) {
            return {};
        }
        var match = String(errorText).match(new RegExp("^" + pattern + "$"));
        if (!match) {
            return null;
        }
        var vars = {};
        names.forEach(function (name, i) {
            vars[name] = match[i + 1];
        });
        return vars;
    }

    function apiErrorMessage(data) {
        if (!data) {
            return t("requestFailed");
        }
        var fallback = data.error || t("requestFailed");
        var code = data.code;
        if (!code) {
            return fallback;
        }
        var localized = t(code);
        if (!localized || localized === code) {
            return fallback;
        }
        if (localized.indexOf("{") === -1) {
            return localized;
        }
        var vars = varsFromEnglishError(code, data.error);
        if (vars) {
            var filled = t(code, vars);
            if (filled.indexOf("{") === -1) {
                return filled;
            }
        }
        return fallback;
    }

    function api(path, method, body) {
        var opts = {
            method: method || "GET",
            headers: { Accept: "application/json", "X-CSRFToken": CSRF },
        };
        if (body !== undefined) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        return fetch(path, opts).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) {
                    throw new Error(apiErrorMessage(data));
                }
                return data;
            });
        });
    }

    function populateItemPicker(items) {
        state.items = items || [];
        fillSelect(
            lineItem,
            state.items.map(function (item) {
                return {
                    value: String(item.id),
                    label: (item.internal_code || "") + " — " + item.description,
                };
            })
        );
    }

    function loadItems() {
        if (!BranchOffline.isOnline()) {
            return BranchDB.getCachedCatalog().then(function (data) {
                var cache = BranchOffline.catalogCacheForBranch(
                    data,
                    document.body.getAttribute("data-branch-id")
                );
                if (!cache.ok) {
                    populateItemPicker([]);
                    showError(cache.message);
                    return;
                }
                populateItemPicker(cache.items);
                showSellingPrices = !!(data.meta && data.meta.show_selling_prices);
            });
        }
        return api("/api/branch/catalog/").then(function (data) {
            applyCommercialMode(data);
            populateItemPicker(data.catalog || []);
            return BranchDB.saveCatalog(data.catalog || [], document.body.getAttribute("data-branch-id"), {
                show_selling_prices: data.show_selling_prices === true,
                commercial_mode: data.commercial_mode || "",
            });
        });
    }

    function loadPending() {
        return BranchDB.getPendingRequests().then(function (rows) {
            state.pending = rows || [];
        });
    }

    function renderList() {
        requestBody.textContent = "";
        state.pending.forEach(function (pending) {
            var tr = document.createElement("tr");
            if (pending.client_uuid === state.selectedClientUuid) {
                tr.className = "selected";
            }
            tr.appendChild(el("td", pending.client_uuid.slice(0, 8) + "…"));
            tr.appendChild(el("td", t("statusPendingSync"), "status"));
            tr.appendChild(el("td", new Date(pending.created_at).toLocaleString(dateLocale())));
            tr.addEventListener("click", function () {
                selectPending(pending.client_uuid);
            });
            requestBody.appendChild(tr);
        });
        state.requests.forEach(function (req) {
            var tr = document.createElement("tr");
            if (req.id === state.selectedId) {
                tr.className = "selected";
            }
            tr.appendChild(el("td", req.id));
            tr.appendChild(el("td", statusLabel(req.status), "status"));
            tr.appendChild(el("td", new Date(req.created_at).toLocaleString(dateLocale())));
            tr.addEventListener("click", function () {
                selectRequest(req.id);
            });
            requestBody.appendChild(tr);
        });
    }

    function loadRequests() {
        if (!BranchOffline.isOnline()) {
            return loadPending().then(function () {
                renderList();
            });
        }
        return Promise.all([api("/api/branch/requests/"), loadPending()]).then(function (results) {
            applyCommercialMode(results[0]);
            state.requests = results[0].requests || [];
            renderList();
        });
    }

    function renderDetail(req) {
        renderLineHead();
        detailTitle.textContent = t("detailTitleNum", { id: req.id });
        detailMeta.textContent = t("statusLabel", { status: statusLabel(req.status) });
        if (showSellingPrices && req.totals) {
            detailTotals.hidden = false;
            detailTotals.textContent = t("totals", {
                net: req.totals.net,
                vat: req.totals.vat,
                gross: req.totals.gross,
            });
        } else {
            detailTotals.textContent = "";
            detailTotals.hidden = true;
        }

        lineBody.textContent = "";
        req.lines.forEach(function (line) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", line.internal_code));
            tr.appendChild(el("td", line.description));
            tr.appendChild(el("td", line.quantity));
            if (showSellingPrices) {
                tr.appendChild(el("td", line.unit_price));
            }
            var td = document.createElement("td");
            if (req.status === "draft" && BranchOffline.isOnline()) {
                var btn = el("button", t("remove"), "btn");
                btn.addEventListener("click", function () {
                    removeLine(req.id, line.id);
                });
                td.appendChild(btn);
            }
            tr.appendChild(td);
            lineBody.appendChild(tr);
        });

        var isDraft = req.status === "draft";
        lineForm.hidden = !isDraft || !BranchOffline.isOnline();

        actions.textContent = "";
        actions.hidden = false;
        if (isDraft && BranchOffline.isOnline()) {
            addAction(t("submit"), function () {
                action(req.id, "submit");
            }, true);
            addAction(t("cancelRequest"), function () {
                if (confirmPermanentCancel(req.id)) {
                    action(req.id, "cancel");
                }
            });
        } else if (req.status === "submitted" && CAN_APPROVE && BranchOffline.isOnline()) {
            addAction(t("approve"), function () {
                var confirmMsg =
                    showSellingPrices && req.totals
                        ? t("approveConfirmGross", { id: req.id, gross: req.totals.gross })
                        : t("approveConfirm", { id: req.id });
                if (confirm(confirmMsg)) {
                    action(req.id, "approve");
                }
            }, true);
            addAction(t("reject"), function () {
                var reason = prompt(t("rejectPrompt"));
                if (reason !== null) {
                    action(req.id, "reject", { reason: reason });
                }
            });
        } else if (req.status === "approved" && CAN_APPROVE && BranchOffline.isOnline()) {
            addAction(t("cancelRequest"), function () {
                if (!confirmPermanentCancel(req.id)) {
                    return;
                }
                var reason = prompt(t("cancelReasonPrompt"));
                if (reason !== null) {
                    action(req.id, "cancel", { reason: reason });
                }
            });
        } else if (!BranchOffline.isOnline()) {
            addAction(t("offline"), null);
            actions.lastChild.disabled = true;
            actions.lastChild.textContent = t("offlineNeedWifi");
        }
    }

    function renderPendingDetail(pending) {
        renderLineHead();
        detailTitle.textContent = t("pendingSync");
        detailMeta.textContent = t("pendingStatus", {
            detail: pending.last_error ? pending.last_error : t("waitingWifi"),
        });
        if (showSellingPrices) {
            var net = 0;
            pending.lines.forEach(function (line) {
                var priced = state.items.find(function (i) {
                    return String(i.id) === String(line.item_id);
                });
                if (priced && priced.retail_price) {
                    net += parseFloat(priced.retail_price) * parseFloat(line.quantity);
                }
            });
            detailTotals.hidden = false;
            detailTotals.textContent = t("estimatedNet", { net: net.toFixed(2) });
        } else {
            detailTotals.textContent = "";
            detailTotals.hidden = true;
        }

        lineBody.textContent = "";
        pending.lines.forEach(function (line) {
            var item = state.items.find(function (i) {
                return String(i.id) === String(line.item_id);
            });
            var tr = document.createElement("tr");
            tr.appendChild(el("td", item ? item.internal_code : line.item_id));
            tr.appendChild(el("td", item ? item.description : ""));
            tr.appendChild(el("td", line.quantity));
            if (showSellingPrices) {
                tr.appendChild(el("td", item ? item.retail_price : ""));
            }
            tr.appendChild(el("td", ""));
            lineBody.appendChild(tr);
        });

        lineForm.hidden = false;
        actions.textContent = "";
        actions.hidden = false;
        if (!BranchOffline.isOnline()) {
            addAction(t("offline"), null);
            actions.lastChild.disabled = true;
            actions.lastChild.textContent = t("offlineWillSync");
        }
    }

    function confirmPermanentCancel(requestId) {
        return confirm(t("cancelConfirm", { id: requestId }));
    }

    function addAction(label, fn, primary) {
        var btn = el("button", label, primary ? "btn btn-primary" : "btn");
        if (fn) {
            btn.addEventListener("click", fn);
        }
        actions.appendChild(btn);
    }

    function selectRequest(id) {
        state.selectedId = id;
        state.selectedClientUuid = null;
        clearError();
        if (!BranchOffline.isOnline()) {
            showError(t("detailsNeedWifi"));
            return;
        }
        api("/api/branch/requests/" + id + "/")
            .then(function (data) {
                applyCommercialMode(data);
                renderDetail(data.request);
                renderList();
            })
            .catch(showError);
    }

    function selectPending(clientUuid) {
        state.selectedId = null;
        state.selectedClientUuid = clientUuid;
        clearError();
        var pending = state.pending.find(function (p) {
            return p.client_uuid === clientUuid;
        });
        if (pending) {
            renderPendingDetail(pending);
            renderList();
        }
    }

    function action(id, name, body) {
        clearError();
        api("/api/branch/requests/" + id + "/" + name + "/", "POST", body || {})
            .then(function () {
                return loadRequests();
            })
            .then(function () {
                return selectRequest(id);
            })
            .catch(showError);
    }

    function addLine() {
        var itemId = lineItem.value;
        var qty = document.getElementById("line-qty").value;
        if (!itemId || !qty) {
            showError(t("chooseItemQty"));
            return;
        }
        clearError();

        if (state.selectedClientUuid) {
            var pending = state.pending.find(function (p) {
                return p.client_uuid === state.selectedClientUuid;
            });
            if (!pending) {
                showError(t("pendingNotFound"));
                return;
            }
            if (pending.status === "syncing") {
                showError(t("syncInProgress"));
                return;
            }
            pending.lines = pending.lines || [];
            if (
                pending.lines.some(function (line) {
                    return String(line.item_id) === String(itemId);
                })
            ) {
                showError(t("itemAlreadyOnRequest"));
                return;
            }
            pending.lines.push({
                client_line_uuid: BranchOffline.newClientUuid(),
                item_id: parseInt(itemId, 10),
                quantity: qty,
            });
            BranchDB.putPendingRequest(pending)
                .then(function () {
                    return loadPending();
                })
                .then(function () {
                    selectPending(state.selectedClientUuid);
                })
                .catch(showError);
            return;
        }

        if (!state.selectedId) {
            showError(t("selectRequestFirst"));
            return;
        }
        api("/api/branch/requests/" + state.selectedId + "/lines/", "POST", {
            item_id: itemId,
            quantity: qty,
        })
            .then(function () {
                return selectRequest(state.selectedId);
            })
            .catch(showError);
    }

    function removeLine(requestId, lineId) {
        clearError();
        api("/api/branch/requests/" + requestId + "/lines/" + lineId + "/remove/", "DELETE")
            .then(function () {
                return selectRequest(requestId);
            })
            .catch(showError);
    }

    function createOfflineRequest() {
        var entry = {
            client_uuid: BranchOffline.newClientUuid(),
            branch_id: document.body.getAttribute("data-branch-id"),
            user_id: document.body.getAttribute("data-user-id"),
            status: "pending",
            created_at: new Date().toISOString(),
            notes: "",
            lines: [],
            last_error: "",
        };
        return BranchDB.putPendingRequest(entry).then(function () {
            return loadPending().then(function () {
                selectPending(entry.client_uuid);
            });
        });
    }

    function createOnlineRequest() {
        return api("/api/branch/requests/create/", "POST", {}).then(function (data) {
            return loadRequests().then(function () {
                selectRequest(data.request.id);
            });
        });
    }

    function refreshView() {
        applyStaticI18n();
        renderList();
        if (state.selectedId) {
            selectRequest(state.selectedId);
            return;
        }
        if (state.selectedClientUuid) {
            selectPending(state.selectedClientUuid);
        }
    }

    newRequestBtn.addEventListener("click", function () {
        clearError();
        if (BranchOffline.isOnline()) {
            createOnlineRequest().catch(showError);
        } else {
            createOfflineRequest().catch(showError);
        }
    });
    document.getElementById("add-line").addEventListener("click", addLine);

    window.addEventListener("branch-sync-complete", function () {
        loadRequests().catch(showError);
    });
    document.addEventListener("cc-lang-changed", refreshView);

    applyStaticI18n();
    loadItems()
        .then(loadRequests)
        .catch(showError);
}());
