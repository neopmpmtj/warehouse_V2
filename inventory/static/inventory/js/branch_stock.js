"use strict";

(function () {
    var LANG_KEY = "cc-lang";
    var NUMERIC_SORT_KEYS = { on_hand: true };

    var state = {
        items: [],
        search: "",
        family: "",
        subFamily: "",
        sortKey: "description",
        sortDir: "asc",
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
        var dict = BRANCH_STOCK_I18N[currentLang()] || BRANCH_STOCK_I18N.en;
        var text = dict[key] !== undefined ? dict[key] : (BRANCH_STOCK_I18N.en[key] || key);
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
        var dict = BRANCH_STOCK_I18N[currentLang()] || BRANCH_STOCK_I18N.en;
        scope.querySelectorAll("[data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key && dict[key] !== undefined) {
                node.textContent = t(key);
            }
        });
        scope.querySelectorAll("[data-i18n-placeholder]").forEach(function (node) {
            var key = node.getAttribute("data-i18n-placeholder");
            if (key && dict[key] !== undefined) {
                node.setAttribute("placeholder", t(key));
            }
        });
        scope.querySelectorAll("[data-i18n-aria]").forEach(function (node) {
            var key = node.getAttribute("data-i18n-aria");
            if (key && dict[key] !== undefined) {
                node.setAttribute("aria-label", t(key));
            }
        });
    }

    function uniqueFamilies(rows) {
        var seen = {};
        var names = [];
        rows.forEach(function (row) {
            var name = row.family || "";
            if (!name || seen[name]) {
                return;
            }
            seen[name] = true;
            names.push(name);
        });
        return names;
    }

    function uniqueSubFamilies(rows, familyName) {
        var seen = {};
        var options = [];
        rows.forEach(function (row) {
            var sub = row.sub_family || "";
            if (!sub) {
                return;
            }
            if (familyName && row.family !== familyName) {
                return;
            }
            var value = familyName ? sub : row.family + "||" + sub;
            if (seen[value]) {
                return;
            }
            seen[value] = true;
            options.push({
                value: value,
                label: familyName ? sub : row.family + " / " + sub,
            });
        });
        return options;
    }

    function fillFamilyFilter() {
        var select = document.getElementById("stock-family");
        if (!select || typeof fillSelect !== "function") {
            return;
        }
        fillSelect(
            select,
            [{ value: "", label: t("allFamilies") }].concat(
                uniqueFamilies(state.items).map(function (name) {
                    return { value: name, label: name };
                })
            )
        );
        select.value = state.family || "";
        if (select.value !== state.family) {
            state.family = "";
            select.value = "";
        }
    }

    function fillSubFamilyFilter() {
        var select = document.getElementById("stock-sub-family");
        if (!select || typeof fillSelect !== "function") {
            return;
        }
        var options = uniqueSubFamilies(state.items, state.family);
        fillSelect(
            select,
            [{ value: "", label: t("allSubFamilies") }].concat(options)
        );
        if (
            state.subFamily &&
            options.some(function (option) {
                return option.value === state.subFamily;
            })
        ) {
            select.value = state.subFamily;
        } else {
            select.value = "";
            state.subFamily = "";
        }
    }

    function filteredItems() {
        var rows = state.items;
        if (state.family) {
            rows = rows.filter(function (item) {
                return item.family === state.family;
            });
        }
        if (state.subFamily) {
            rows = rows.filter(function (item) {
                if (state.family) {
                    return item.sub_family === state.subFamily;
                }
                return item.family + "||" + item.sub_family === state.subFamily;
            });
        }
        var query = state.search.trim().toLowerCase();
        if (query) {
            rows = rows.filter(function (item) {
                return (
                    String(item.internal_code || "").toLowerCase().indexOf(query) !== -1 ||
                    String(item.description || "").toLowerCase().indexOf(query) !== -1
                );
            });
        }
        return rows;
    }

    function numericSortValue(value) {
        if (value === null || value === undefined || value === "") {
            return null;
        }
        var num = Number(value);
        return isNaN(num) ? null : num;
    }

    function sortValue(item, key) {
        if (key === "internal_code") {
            return item.internal_code || "";
        }
        if (key === "description") {
            return item.description || "";
        }
        if (key === "family") {
            return item.family || "";
        }
        if (key === "sub_family") {
            return item.sub_family || "";
        }
        if (key === "unit_of_measure") {
            return item.unit_of_measure || "";
        }
        if (NUMERIC_SORT_KEYS[key]) {
            return numericSortValue(item[key]);
        }
        return item.id;
    }

    function compareItems(left, right, key, dir) {
        var leftVal = sortValue(left, key);
        var rightVal = sortValue(right, key);
        var cmp = 0;
        if (NUMERIC_SORT_KEYS[key]) {
            if (leftVal === null && rightVal === null) {
                cmp = 0;
            } else if (leftVal === null) {
                cmp = 1;
            } else if (rightVal === null) {
                cmp = -1;
            } else {
                cmp = leftVal - rightVal;
            }
        } else {
            cmp = String(leftVal).localeCompare(String(rightVal), currentLang(), {
                sensitivity: "base",
            });
        }
        if (cmp === 0) {
            cmp = (left.id || 0) - (right.id || 0);
        }
        return dir === "desc" ? -cmp : cmp;
    }

    function sortedItems(rows) {
        return rows.slice().sort(function (left, right) {
            return compareItems(left, right, state.sortKey, state.sortDir);
        });
    }

    function updateSortHeaders() {
        document.querySelectorAll(".page .grid th[data-sort]").forEach(function (header) {
            var key = header.getAttribute("data-sort");
            var columnKey = header.getAttribute("data-i18n-col");
            var columnLabel = columnKey ? t(columnKey) : key;
            var button = header.querySelector(".sort-btn");
            var indicator = header.querySelector(".sort-indicator");
            if (!button || !indicator) {
                return;
            }
            if (state.sortKey === key) {
                header.setAttribute("aria-sort", state.sortDir === "asc" ? "ascending" : "descending");
                header.classList.add("is-sorted");
                indicator.textContent = state.sortDir === "asc" ? "▲" : "▼";
                button.setAttribute(
                    "aria-label",
                    t(state.sortDir === "asc" ? "sortActiveAsc" : "sortActiveDesc", {
                        column: columnLabel,
                    })
                );
                return;
            }
            header.setAttribute("aria-sort", "none");
            header.classList.remove("is-sorted");
            indicator.textContent = "";
            button.setAttribute("aria-label", t("sortBy", { column: columnLabel }));
        });
    }

    function toggleSort(key) {
        if (state.sortKey === key) {
            state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
            return;
        }
        state.sortKey = key;
        state.sortDir = "asc";
    }

    function td(text) {
        var cell = document.createElement("td");
        cell.textContent = text == null || text === "" ? t("dash") : String(text);
        return cell;
    }

    function render() {
        var body = document.getElementById("stock-body");
        var empty = document.getElementById("stock-empty");
        if (!body) {
            return;
        }
        body.replaceChildren();
        var rows = sortedItems(filteredItems());
        if (!rows.length) {
            if (empty) {
                empty.hidden = false;
                empty.textContent = state.items.length ? t("noMatch") : t("empty");
            }
            updateSortHeaders();
            return;
        }
        if (empty) {
            empty.hidden = true;
        }
        rows.forEach(function (item) {
            var tr = document.createElement("tr");
            tr.appendChild(td(item.internal_code));
            tr.appendChild(td(item.description));
            tr.appendChild(td(item.family));
            tr.appendChild(td(item.sub_family));
            tr.appendChild(td(item.unit_of_measure));
            tr.appendChild(td(item.on_hand));
            body.appendChild(tr);
        });
        updateSortHeaders();
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

    function load() {
        if (typeof BranchOffline !== "undefined" && !BranchOffline.isOnline()) {
            state.items = [];
            showOffline(t("offlineBanner"));
            fillFamilyFilter();
            fillSubFamilyFilter();
            render();
            return;
        }
        showOffline("");
        fetch("/api/branch/stock/", { credentials: "same-origin", headers: { Accept: "application/json" } })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("load");
                }
                return response.json();
            })
            .then(function (payload) {
                showBanner("");
                state.items = payload.items || [];
                fillFamilyFilter();
                fillSubFamilyFilter();
                render();
            })
            .catch(function () {
                showBanner(t("loadFailed"));
            });
    }

    function bindEvents() {
        var search = document.getElementById("stock-search");
        if (search) {
            search.addEventListener("input", function () {
                state.search = search.value;
                render();
            });
        }
        var family = document.getElementById("stock-family");
        if (family) {
            family.addEventListener("change", function () {
                state.family = family.value;
                fillSubFamilyFilter();
                render();
            });
        }
        var subFamily = document.getElementById("stock-sub-family");
        if (subFamily) {
            subFamily.addEventListener("change", function () {
                state.subFamily = subFamily.value;
                render();
            });
        }
        document.querySelectorAll(".page .grid th[data-sort]").forEach(function (header) {
            var button = header.querySelector(".sort-btn");
            if (!button) {
                return;
            }
            button.addEventListener("click", function () {
                toggleSort(header.getAttribute("data-sort"));
                render();
            });
        });
        window.addEventListener("cc-lang-changed", function () {
            applyStaticI18n();
            fillFamilyFilter();
            fillSubFamilyFilter();
            render();
        });
    }

    applyStaticI18n();
    bindEvents();
    load();
})();
