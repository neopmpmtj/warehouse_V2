"use strict";

var BranchSyncQueue = (function () {
    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : "";
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

    function drainQueue() {
        if (!BranchOffline.isOnline()) {
            return Promise.resolve({ synced: 0, failed: 0 });
        }
        return BranchDB.getPendingRequests().then(function (entries) {
            var pending = entries.filter(function (e) {
                return e.status === "pending" || e.status === "failed";
            });
            var synced = 0;
            var failed = 0;
            var chain = Promise.resolve();
            pending.forEach(function (entry) {
                chain = chain.then(function () {
                    return BranchDB.updatePendingRequest(entry.client_uuid, { status: "syncing" })
                        .then(function () {
                            return syncOne(entry);
                        })
                        .then(function () {
                            return BranchDB.deletePendingRequest(entry.client_uuid);
                        })
                        .then(function () {
                            synced += 1;
                        })
                        .catch(function (err) {
                            failed += 1;
                            return BranchDB.updatePendingRequest(entry.client_uuid, {
                                status: "failed",
                                last_error: err.message || "Sync failed.",
                            });
                        });
                });
            });
            return chain.then(function () {
                return { synced: synced, failed: failed };
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
