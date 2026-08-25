"use strict";

(function () {
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var CAN_APPROVE = document.body.getAttribute("data-can-approve") === "true";
    var state = { selectedId: null, selectedClientUuid: null, requests: [], pending: [], items: [] };

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
        banner.textContent = msg || "Request failed.";
        banner.hidden = false;
    }

    function clearError() {
        banner.hidden = true;
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
                    throw new Error(data.error || "HTTP " + resp.status);
                }
                return data;
            });
        });
    }

    function populateItemPicker(items) {
        state.items = items || [];
        lineItem.textContent = "";
        state.items.forEach(function (item) {
            var opt = document.createElement("option");
            opt.value = item.id;
            opt.textContent = (item.internal_code || "") + " — " + item.description;
            lineItem.appendChild(opt);
        });
    }

    function loadItems() {
        if (!BranchOffline.isOnline()) {
            return BranchDB.getCachedCatalog().then(function (data) {
                populateItemPicker(data.items);
            });
        }
        return api("/api/branch/catalog/").then(function (data) {
            populateItemPicker(data.catalog || []);
            return BranchDB.saveCatalog(data.catalog || [], document.body.getAttribute("data-branch-id"));
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
            tr.appendChild(el("td", "pending sync", "status"));
            tr.appendChild(el("td", new Date(pending.created_at).toLocaleString()));
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
            tr.appendChild(el("td", req.status, "status"));
            tr.appendChild(el("td", new Date(req.created_at).toLocaleString()));
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
            state.requests = results[0].requests || [];
            renderList();
        });
    }

    function renderDetail(req) {
        detailTitle.textContent = "Request #" + req.id;
        detailMeta.textContent = "Status: " + req.status;
        detailTotals.textContent =
            "Net " + req.totals.net + " · VAT " + req.totals.vat + " · Gross " + req.totals.gross;

        lineBody.textContent = "";
        req.lines.forEach(function (line) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", line.internal_code));
            tr.appendChild(el("td", line.description));
            tr.appendChild(el("td", line.quantity));
            tr.appendChild(el("td", line.unit_price));
            var td = document.createElement("td");
            if (req.status === "draft" && BranchOffline.isOnline()) {
                var btn = el("button", "Remove", "btn");
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
        if (isDraft && BranchOffline.isOnline()) {
            addAction("Submit", function () {
                action(req.id, "submit");
            }, true);
            addAction("Cancel", function () {
                action(req.id, "cancel");
            });
        } else if (req.status === "submitted" && CAN_APPROVE && BranchOffline.isOnline()) {
            addAction("Approve", function () {
                if (confirm("Approve request #" + req.id + " for " + req.totals.gross + " gross?")) {
                    action(req.id, "approve");
                }
            }, true);
            addAction("Reject", function () {
                var reason = prompt("Reason for rejection:");
                if (reason !== null) {
                    action(req.id, "reject", { reason: reason });
                }
            });
        } else if (req.status === "approved" && CAN_APPROVE && BranchOffline.isOnline()) {
            addAction("Cancel", function () {
                var reason = prompt("Reason for cancellation:");
                if (reason !== null) {
                    action(req.id, "cancel", { reason: reason });
                }
            });
        } else if (!BranchOffline.isOnline()) {
            addAction("Offline", null);
            actions.lastChild.disabled = true;
            actions.lastChild.textContent = "Connect to Wi-Fi to submit or approve";
        }
    }

    function renderPendingDetail(pending) {
        detailTitle.textContent = "Pending sync";
        detailMeta.textContent =
            "Status: draft (local) · " + (pending.last_error ? pending.last_error : "Waiting for Wi-Fi");
        var net = 0;
        pending.lines.forEach(function (line) {
            var item = state.items.find(function (i) {
                return String(i.id) === String(line.item_id);
            });
            if (item && item.wholesale_price) {
                net += parseFloat(item.wholesale_price) * parseFloat(line.quantity);
            }
        });
        detailTotals.textContent = "Estimated net (local): " + net.toFixed(2);

        lineBody.textContent = "";
        pending.lines.forEach(function (line) {
            var item = state.items.find(function (i) {
                return String(i.id) === String(line.item_id);
            });
            var tr = document.createElement("tr");
            tr.appendChild(el("td", item ? item.internal_code : line.item_id));
            tr.appendChild(el("td", item ? item.description : ""));
            tr.appendChild(el("td", line.quantity));
            tr.appendChild(el("td", item ? item.wholesale_price : ""));
            tr.appendChild(el("td", ""));
            lineBody.appendChild(tr);
        });

        lineForm.hidden = false;
        actions.textContent = "";
        if (!BranchOffline.isOnline()) {
            addAction("Offline", null);
            actions.lastChild.disabled = true;
            actions.lastChild.textContent = "Will sync when online";
        }
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
            showError("Request details require Wi-Fi.");
            return;
        }
        api("/api/branch/requests/" + id + "/")
            .then(function (data) {
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
            showError("Choose an item and a quantity.");
            return;
        }
        clearError();

        if (state.selectedClientUuid) {
            var pending = state.pending.find(function (p) {
                return p.client_uuid === state.selectedClientUuid;
            });
            if (!pending) {
                showError("Pending request not found.");
                return;
            }
            pending.lines = pending.lines || [];
            if (
                pending.lines.some(function (line) {
                    return String(line.item_id) === String(itemId);
                })
            ) {
                showError("Item already on this request.");
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
            showError("Select a request first.");
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

    newRequestBtn.addEventListener("click", function () {
        clearError();
        if (BranchOffline.isOnline()) {
            createOnlineRequest().catch(showError);
        } else {
            createOfflineRequest().catch(showError);
        }
    });
    document.getElementById("add-line").addEventListener("click", addLine);

    BranchOffline.bindOfflineBanner("offline-banner");
    BranchSyncQueue.bindAutoSync(function () {
        loadRequests().catch(showError);
    });

    loadItems()
        .then(loadRequests)
        .catch(showError);
}());
