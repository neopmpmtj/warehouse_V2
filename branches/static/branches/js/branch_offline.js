"use strict";

var BranchOffline = (function () {
    function isOnline() {
        return typeof navigator.onLine === "boolean" ? navigator.onLine : true;
    }

    function showOfflineBanner(el) {
        if (!el) {
            return;
        }
        if (isOnline()) {
            el.hidden = true;
            return;
        }
        el.textContent = "You are offline. Some actions require Wi-Fi.";
        el.hidden = false;
    }

    function bindOfflineBanner(elementId) {
        var el = document.getElementById(elementId || "offline-banner");
        if (!el) {
            return;
        }
        function refresh() {
            showOfflineBanner(el);
        }
        window.addEventListener("online", refresh);
        window.addEventListener("offline", refresh);
        refresh();
    }

    function newClientUuid() {
        if (window.crypto && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            var r = (Math.random() * 16) | 0;
            var v = c === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function catalogCacheForBranch(data, branchId) {
        var items = data && data.items ? data.items : [];
        var meta = data && data.meta ? data.meta : null;
        if (!meta || meta.branch_id == null || meta.branch_id === "") {
            return { ok: true, items: items };
        }
        if (!branchId) {
            return { ok: true, items: items };
        }
        if (String(meta.branch_id) === String(branchId)) {
            return { ok: true, items: items };
        }
        return {
            ok: false,
            items: [],
            message:
                "Cached catalogue is for another branch. Connect to Wi-Fi to download this branch's catalogue.",
        };
    }

    return {
        isOnline: isOnline,
        bindOfflineBanner: bindOfflineBanner,
        newClientUuid: newClientUuid,
        catalogCacheForBranch: catalogCacheForBranch,
    };
}());
