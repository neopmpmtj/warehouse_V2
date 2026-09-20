"use strict";

(function () {
    var LANG_KEY = "cc-lang";
    var CSRF = document.querySelector('meta[name="csrf-token"]').content;
    var state = { rows: [], branches: [], branchId: "" };

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

    function t(key) {
        var dict = STOCK_AT_BRANCHES_I18N[currentLang()] || STOCK_AT_BRANCHES_I18N.en;
        return dict[key] !== undefined ? dict[key] : (STOCK_AT_BRANCHES_I18N.en[key] || key);
    }

    function applyStaticI18n() {
        document.documentElement.lang = currentLang() === "pt" ? "pt-PT" : "en";
        document.title = t("title") + " — CentCompras";
        var dict = STOCK_AT_BRANCHES_I18N[currentLang()] || STOCK_AT_BRANCHES_I18N.en;
        document.querySelectorAll("[data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key && dict[key] !== undefined) {
                node.textContent = t(key);
            }
        });
    }

    function el(tag, text) {
        var node = document.createElement(tag);
        if (text != null) {
            node.textContent = text;
        }
        return node;
    }

    function showBanner(message) {
        var banner = document.getElementById("banner");
        if (!banner) {
            return;
        }
        banner.textContent = message || "";
        banner.hidden = !message;
    }

    function fillBranchFilter() {
        var select = document.getElementById("branch-filter");
        if (!select || typeof fillSelect !== "function") {
            return;
        }
        var current = state.branchId;
        fillSelect(
            select,
            state.branches.map(function (branch) {
                return { value: String(branch.id), label: branch.name };
            }),
            t("allBranches")
        );
        if (current) {
            select.value = current;
        }
    }

    function visibleRows() {
        if (!state.branchId) {
            return state.rows;
        }
        return state.rows.filter(function (row) {
            return String(row.branch_id) === String(state.branchId);
        });
    }

    function render() {
        var body = document.getElementById("stock-body");
        var empty = document.getElementById("empty");
        if (!body) {
            return;
        }
        body.replaceChildren();
        var rows = visibleRows();
        if (empty) {
            empty.hidden = rows.length > 0;
            empty.textContent = t("empty");
        }
        rows.forEach(function (row) {
            var tr = document.createElement("tr");
            tr.appendChild(el("td", row.branch_name || t("dash")));
            tr.appendChild(el("td", row.internal_code || t("dash")));
            tr.appendChild(el("td", row.description || t("dash")));
            tr.appendChild(el("td", row.on_hand));
            tr.appendChild(el("td", row.is_active ? t("active") : t("inactive")));
            body.appendChild(tr);
        });
    }

    function load() {
        var path = "/api/manage/stock-at-branches/";
        fetch(path, {
            credentials: "same-origin",
            headers: { Accept: "application/json", "X-CSRFToken": CSRF },
        }).then(function (response) {
            return response.json().then(function (data) {
                if (!response.ok) {
                    throw new Error((data && data.error) || t("loadFailed"));
                }
                return data;
            });
        }).then(function (payload) {
            state.rows = payload.rows || [];
            state.branches = payload.branches || [];
            fillBranchFilter();
            render();
        }).catch(function () {
            showBanner(t("loadFailed"));
        });
    }

    function bindEvents() {
        var select = document.getElementById("branch-filter");
        if (select) {
            select.addEventListener("change", function () {
                state.branchId = select.value;
                render();
            });
        }
        window.addEventListener("cc-lang-changed", function () {
            applyStaticI18n();
            fillBranchFilter();
            render();
        });
    }

    applyStaticI18n();
    bindEvents();
    load();
})();
