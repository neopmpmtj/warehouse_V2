"use strict";

var BranchSyncQueue = (function () {
    var SYNC_STALE_MS = 60000;

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : "";
    }

    function getCurrentBranchId() {
        return document.body.getAttribute("data-branch-id");
    }

    function isWrongBranch(entry) {
        var current = getCurrentBranchId();
        if (!current || entry.branch_id == null || entry.branch_id === "") {
            return false;
        }
        return String(entry.branch_id) !== String(current);
    }

    function isStaleSyncing(entry) {
        if (entry.status !== "syncing") {
            return false;
        }
        if (!entry.syncing_at) {
            return true;
        }
        return Date.now() - Date.parse(entry.syncing_at) > SYNC_STALE_MS;
    }

    function isEligibleForDrain(entry) {
        if (entry.status === "pending" || entry.status === "failed") {
            return true;
        }
        return isStaleSyncing(entry);
    }

    function resetStaleSyncing(entries) {
        var chain = Promise.resolve();
        entries.forEach(function (entry) {
            if (!isStaleSyncing(entry)) {
                return;
            }
            chain = chain.then(function () {
                return BranchDB.updatePendingRequest(entry.client_uuid, {
                    status: "pending",
                    syncing_at: null,
                });
            });
        });
        return chain;
    }

    function lineKey(line) {
        return String(line.item_id);
    }

    function findExtraLines(snapshotLines, currentLines) {
        var sent = {};
        (snapshotLines || []).forEach(function (line) {
            sent[lineKey(line)] = true;
        });
        return (currentLines || []).filter(function (line) {
            return !sent[lineKey(line)];
        });
    }

    function syncOne(entry) {
        return fetch("/api/branch/requests/sync/", {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({
                client_uuid: entry.client_uuid,
                notes: entry.notes || "",
                lines: entry.lines || [],
            }),
        }).then(function (resp) {
            return resp.json().then(function (data) {
                if (!resp.ok) {
                    var err = new Error(data.error || "HTTP " + resp.status);
                    err.code = data.code;
                    throw err;
                }
                return data;
            });
        });
    }

    function addLinesToServer(requestId, lines) {
        var chain = Promise.resolve();
        lines.forEach(function (line) {
            chain = chain.then(function () {
                return fetch("/api/branch/requests/" + requestId + "/lines/", {
                    method: "POST",
                    headers: {
                        Accept: "application/json",
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken(),
                    },
                    body: JSON.stringify({
                        item_id: line.item_id,
                        quantity: line.quantity,
                    }),
                }).then(function (resp) {
                    return resp.json().then(function (data) {
                        if (!resp.ok) {
                            var err = new Error(data.error || "HTTP " + resp.status);
                            err.code = data.code;
                            throw err;
                        }
                        return data;
                    });
                });
            });
        });
        return chain;
    }

    function processEntry(entry) {
        var snapshotLines = (entry.lines || []).slice();
        return BranchDB.updatePendingRequest(entry.client_uuid, {
            status: "syncing",
            syncing_at: new Date().toISOString(),
        })
            .then(function () {
                return syncOne(entry);
            })
            .then(function (data) {
                return BranchDB.getPendingRequest(entry.client_uuid).then(function (current) {
                    if (!current) {
                        return;
                    }
                    var extra = findExtraLines(snapshotLines, current.lines);
                    var requestId = data.request && data.request.id;
                    if (extra.length && requestId) {
                        return addLinesToServer(requestId, extra).then(function () {
                            return BranchDB.deletePendingRequest(entry.client_uuid);
                        });
                    }
                    if (extra.length) {
                        return BranchDB.updatePendingRequest(entry.client_uuid, {
                            status: "pending",
                            syncing_at: null,
                        });
                    }
                    return BranchDB.deletePendingRequest(entry.client_uuid);
                });
            });
    }

    function drainQueue() {
        if (!BranchOffline.isOnline()) {
            return Promise.resolve({ synced: 0, failed: 0, skipped: 0 });
        }
        return BranchDB.getPendingRequests()
            .then(resetStaleSyncing)
            .then(function () {
                return BranchDB.getPendingRequests();
            })
            .then(function (entries) {
                var pending = entries.filter(isEligibleForDrain);
                var synced = 0;
                var failed = 0;
                var skipped = 0;
                var chain = Promise.resolve();
                pending.forEach(function (entry) {
                    chain = chain.then(function () {
                        if (isWrongBranch(entry)) {
                            skipped += 1;
                            return;
                        }
                        return processEntry(entry)
                            .then(function () {
                                synced += 1;
                            })
                            .catch(function (err) {
                                failed += 1;
                                return BranchDB.updatePendingRequest(entry.client_uuid, {
                                    status: "failed",
                                    syncing_at: null,
                                    last_error: err.message || "Sync failed.",
                                });
                            });
                    });
                });
                return chain.then(function () {
                    return { synced: synced, failed: failed, skipped: skipped };
                });
            });
    }

    function bindAutoSync(onComplete) {
        function run() {
            drainQueue().then(function (result) {
                if (onComplete) {
                    onComplete(result);
                }
            });
        }
        window.addEventListener("online", run);
        run();
    }

    return {
        drainQueue: drainQueue,
        bindAutoSync: bindAutoSync,
    };
}());
