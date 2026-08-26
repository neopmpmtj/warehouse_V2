/* global indexedDB */
"use strict";

var BranchDB = (function () {
    var DB_NAME = "centcompras_branch";
    var DB_VERSION = 1;
    var CATALOG_ITEMS = "catalog_items";
    var CATALOG_META = "catalog_meta";
    var PENDING_REQUESTS = "pending_requests";

    function openDatabase() {
        return new Promise(function (resolve, reject) {
            var request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = function (event) {
                var db = event.target.result;
                if (!db.objectStoreNames.contains(CATALOG_ITEMS)) {
                    db.createObjectStore(CATALOG_ITEMS, { keyPath: "id" });
                }
                if (!db.objectStoreNames.contains(CATALOG_META)) {
                    db.createObjectStore(CATALOG_META, { keyPath: "key" });
                }
                if (!db.objectStoreNames.contains(PENDING_REQUESTS)) {
                    db.createObjectStore(PENDING_REQUESTS, { keyPath: "client_uuid" });
                }
            };
            request.onsuccess = function () {
                resolve(request.result);
            };
            request.onerror = function () {
                reject(request.error);
            };
        });
    }

    function saveCatalog(items, branchId) {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction([CATALOG_ITEMS, CATALOG_META], "readwrite");
                var itemStore = tx.objectStore(CATALOG_ITEMS);
                var metaStore = tx.objectStore(CATALOG_META);
                itemStore.clear();
                (items || []).forEach(function (item) {
                    itemStore.put(item);
                });
                metaStore.put({
                    key: "catalog",
                    last_updated: new Date().toISOString(),
                    branch_id: branchId || null,
                });
                tx.oncomplete = function () {
                    resolve();
                };
                tx.onerror = function () {
                    reject(tx.error);
                };
            });
        });
    }

    function getCachedCatalog() {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction([CATALOG_ITEMS, CATALOG_META], "readonly");
                var itemsReq = tx.objectStore(CATALOG_ITEMS).getAll();
                var metaReq = tx.objectStore(CATALOG_META).get("catalog");
                var result = { items: [], meta: null };
                itemsReq.onsuccess = function () {
                    result.items = itemsReq.result || [];
                };
                metaReq.onsuccess = function () {
                    result.meta = metaReq.result || null;
                };
                tx.oncomplete = function () {
                    resolve(result);
                };
                tx.onerror = function () {
                    reject(tx.error);
                };
            });
        });
    }

    function putPendingRequest(entry) {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(PENDING_REQUESTS, "readwrite");
                tx.objectStore(PENDING_REQUESTS).put(entry);
                tx.oncomplete = function () {
                    resolve();
                };
                tx.onerror = function () {
                    reject(tx.error);
                };
            });
        });
    }

    function getPendingRequests() {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(PENDING_REQUESTS, "readonly");
                var req = tx.objectStore(PENDING_REQUESTS).getAll();
                req.onsuccess = function () {
                    resolve(req.result || []);
                };
                req.onerror = function () {
                    reject(req.error);
                };
            });
        });
    }

    function getPendingRequest(clientUuid) {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(PENDING_REQUESTS, "readonly");
                var req = tx.objectStore(PENDING_REQUESTS).get(clientUuid);
                req.onsuccess = function () {
                    resolve(req.result || null);
                };
                req.onerror = function () {
                    reject(req.error);
                };
            });
        });
    }

    function deletePendingRequest(clientUuid) {
        return openDatabase().then(function (db) {
            return new Promise(function (resolve, reject) {
                var tx = db.transaction(PENDING_REQUESTS, "readwrite");
                tx.objectStore(PENDING_REQUESTS).delete(clientUuid);
                tx.oncomplete = function () {
                    resolve();
                };
                tx.onerror = function () {
                    reject(tx.error);
                };
            });
        });
    }

    function updatePendingRequest(clientUuid, patch) {
        return getPendingRequests().then(function (rows) {
            var row = rows.find(function (r) {
                return r.client_uuid === clientUuid;
            });
            if (!row) {
                return null;
            }
            Object.keys(patch).forEach(function (key) {
                row[key] = patch[key];
            });
            return putPendingRequest(row).then(function () {
                return row;
            });
        });
    }

    function clearAll() {
        return new Promise(function (resolve) {
            var request = indexedDB.deleteDatabase(DB_NAME);
            request.onsuccess = function () {
                resolve();
            };
            request.onerror = function () {
                resolve();
            };
            request.onblocked = function () {
                resolve();
            };
        });
    }

    return {
        saveCatalog: saveCatalog,
        getCachedCatalog: getCachedCatalog,
        putPendingRequest: putPendingRequest,
        getPendingRequests: getPendingRequests,
        getPendingRequest: getPendingRequest,
        deletePendingRequest: deletePendingRequest,
        updatePendingRequest: updatePendingRequest,
        clearAll: clearAll,
    };
}());
