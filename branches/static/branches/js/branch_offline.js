"use strict";

var BranchOffline = (function () {
    var LANG_KEY = "cc-lang";
    var I18N = {
        en: {
            offlineBanner: "You are offline. Some actions require Wi-Fi.",
            wrongBranchCache:
                "Cached catalogue is for another branch. Connect to Wi-Fi to download this branch's catalogue.",
            syncFailed: "Sync failed.",
        },
        "pt-PT": {
            offlineBanner: "Está offline. Algumas acções exigem Wi-Fi.",
            wrongBranchCache:
                "O catálogo em cache é de outra filial. Ligue-se ao Wi-Fi para descarregar o catálogo desta filial.",
            syncFailed: "A sincronização falhou.",
        },
    };
    I18N.pt = I18N["pt-PT"];

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

    function t(key) {
        var dict = I18N[currentLang()] || I18N.en;
        return dict[key] || I18N.en[key] || key;
    }

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
        el.textContent = t("offlineBanner");
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
        document.addEventListener("cc-lang-changed", refresh);
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
            message: t("wrongBranchCache"),
        };
    }

    return {
        isOnline: isOnline,
        bindOfflineBanner: bindOfflineBanner,
        newClientUuid: newClientUuid,
        catalogCacheForBranch: catalogCacheForBranch,
        t: t,
    };
}());
