"use strict";

(function () {
    var body = document.getElementById("catalog-body");
    var empty = document.getElementById("catalog-empty");
    var banner = document.getElementById("banner");
    var head = document.getElementById("catalog-head");
    if (!body || !banner || !head) {
        return;
    }

    var LANG_KEY = "cc-lang";
    var PRICE_KEYS = [
        { key: "retail_price", col: "colRetail" },
        { key: "wholesale_price", col: "colWholesale" },
        { key: "special_price", col: "colSpecial" },
    ];
    var NUMERIC_SORT_KEYS = {
        retail_price: true,
        wholesale_price: true,
        special_price: true,
    };
    var AVAIL_CLASS = { none: "avail-none", low: "avail-low", "in stock": "avail-ok" };
    var PRICE_SORT_KEYS = { retail_price: true, wholesale_price: true, special_price: true };

    var branchId = document.body.getAttribute("data-branch-id");
    var state = {
        items: [],
        search: "",
        family: "",
        subFamily: "",
        sortKey: "description",
        sortDir: "asc",
        withPrices: false,
    };

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
        var dict = BRANCH_CATALOG_I18N[currentLang()] || BRANCH_CATALOG_I18N.en;
        var text = dict[key] || BRANCH_CATALOG_I18N.en[key] || key;
        if (vars) {
            Object.keys(vars).forEach(function (name) {
                text = text.split("{" + name + "}").join(String(vars[name]));
            });
        }
        return text;
    }

    function availabilityLabel(value) {
        if (value === "none") {
            return t("availNone");
        }
        if (value === "low") {
            return t("availLow");
        }
        if (value === "in stock") {
            return t("availInStock");
        }
        return value || "";
    }

    function applyStaticI18n() {
        document.querySelectorAll(".page [data-i18n]").forEach(function (node) {
            var key = node.getAttribute("data-i18n");
            if (key) {
                node.textContent = t(key);
            }
        });
        document.querySelectorAll(".page [data-i18n-placeholder]").forEach(function (node) {
            node.setAttribute("placeholder", t(node.getAttribute("data-i18n-placeholder")));
        });
        document.querySelectorAll(".page [data-i18n-aria]").forEach(function (node) {
            node.setAttribute("aria-label", t(node.getAttribute("data-i18n-aria")));
        });
        updateSortHeaders();
    }

    function cell(text, className) {
        var td = document.createElement("td");
        td.textContent = text == null ? "" : text;
        if (className) {
            td.className = className;
        }
        return td;
    }

    function showSellingPricesFrom(meta) {
        return !!(meta && meta.show_selling_prices === true);
    }

    function createSortableTh(sortKey, colKey) {
        var th = document.createElement("th");
        th.className = "th-sortable";
        th.setAttribute("data-sort", sortKey);
        th.setAttribute("data-i18n-col", colKey);
        th.setAttribute("aria-sort", "none");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "sort-btn";
        var label = document.createElement("span");
        label.setAttribute("data-i18n", colKey);
        label.textContent = t(colKey);
        var indicator = document.createElement("span");
        indicator.className = "sort-indicator";
        indicator.setAttribute("aria-hidden", "true");
        button.appendChild(label);
        button.appendChild(indicator);
        th.appendChild(button);
        return th;
    }

    function ensurePriceHeaders(withPrices) {
        var hasPrices = Boolean(head.querySelector('th[data-sort="retail_price"]'));
        if (withPrices && hasPrices) {
            return;
        }
        PRICE_KEYS.forEach(function (col) {
            var existing = head.querySelector('th[data-sort="' + col.key + '"]');
            if (existing) {
                existing.remove();
            }
        });
        if (!withPrices) {
            if (PRICE_SORT_KEYS[state.sortKey]) {
                state.sortKey = "description";
                state.sortDir = "asc";
            }
            return;
        }
        var availabilityTh = head.querySelector('th[data-sort="availability"]');
        PRICE_KEYS.forEach(function (col) {
            head.insertBefore(createSortableTh(col.key, col.col), availabilityTh);
        });
    }

    function showBanner(message, isInfo) {
        banner.textContent = message;
        banner.hidden = false;
        banner.classList.toggle("banner-info", Boolean(isInfo));
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
        var select = document.getElementById("catalog-family");
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
        var select = document.getElementById("catalog-sub-family");
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
                    String(item.internal_code || "")
                        .toLowerCase()
                        .indexOf(query) !== -1 ||
                    String(item.description || "")
                        .toLowerCase()
                        .indexOf(query) !== -1
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
        if (key === "availability") {
            return availabilityLabel(item.availability);
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
        head.querySelectorAll("th[data-sort]").forEach(function (header) {
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

    function render() {
        ensurePriceHeaders(state.withPrices);
        body.textContent = "";
        var rows = sortedItems(filteredItems());
        rows.forEach(function (row) {
            var tr = document.createElement("tr");
            tr.appendChild(cell(row.internal_code));
            tr.appendChild(cell(row.description));
            tr.appendChild(cell(row.family));
            tr.appendChild(cell(row.sub_family || "—"));
            tr.appendChild(cell(row.unit_of_measure));
            if (state.withPrices) {
                tr.appendChild(cell(row.retail_price));
                tr.appendChild(cell(row.wholesale_price));
                tr.appendChild(cell(row.special_price));
            }
            tr.appendChild(
                cell(availabilityLabel(row.availability), AVAIL_CLASS[row.availability] || "")
            );
            body.appendChild(tr);
        });
        applyStaticI18n();
        if (empty) {
            empty.hidden = rows.length !== 0;
            empty.textContent = t(state.items.length === 0 ? "empty" : "noMatch");
        }
    }

    function setCatalog(rows, withPrices) {
        state.items = rows || [];
        state.withPrices = withPrices === true;
        fillFamilyFilter();
        fillSubFamilyFilter();
        render();
    }

    function formatLastUpdated(iso) {
        if (!iso) {
            return t("unknownTime");
        }
        try {
            return new Date(iso).toLocaleString();
        } catch (error) {
            return iso;
        }
    }

    function loadFromCache() {
        return BranchDB.getCachedCatalog().then(function (data) {
            var cache = BranchOffline.catalogCacheForBranch(data, branchId);
            if (!cache.ok) {
                showBanner(cache.message);
                if (empty) {
                    empty.hidden = true;
                }
                return;
            }
            if (!cache.items.length) {
                showBanner(t("noCachedCatalog"));
                if (empty) {
                    empty.hidden = true;
                }
                return;
            }
            var withPrices = showSellingPricesFrom(data.meta);
            setCatalog(cache.items, withPrices);
            showBanner(
                t("offlineBanner", { when: formatLastUpdated(data.meta && data.meta.last_updated) }),
                true
            );
        });
    }

    function bindEvents() {
        var search = document.getElementById("catalog-search");
        if (search) {
            search.addEventListener("input", function (event) {
                state.search = event.target.value;
                render();
            });
        }
        var familySelect = document.getElementById("catalog-family");
        if (familySelect) {
            familySelect.addEventListener("change", function (event) {
                state.family = event.target.value;
                fillSubFamilyFilter();
                render();
            });
        }
        var subFamilySelect = document.getElementById("catalog-sub-family");
        if (subFamilySelect) {
            subFamilySelect.addEventListener("change", function (event) {
                state.subFamily = event.target.value;
                render();
            });
        }
        head.addEventListener("click", function (event) {
            var button = event.target.closest("th[data-sort] .sort-btn");
            if (!button) {
                return;
            }
            var key = button.closest("th").getAttribute("data-sort");
            toggleSort(key);
            render();
        });
        document.addEventListener("cc-lang-changed", function () {
            fillFamilyFilter();
            fillSubFamilyFilter();
            render();
        });
    }

    bindEvents();
    applyStaticI18n();
    fillFamilyFilter();
    fillSubFamilyFilter();

    fetch("/api/branch/catalog/", { headers: { Accept: "application/json" } })
        .then(function (resp) {
            if (!resp.ok) {
                return resp.json().then(function (data) {
                    throw new Error(data.error || "HTTP " + resp.status);
                });
            }
            return resp.json();
        })
        .then(function (data) {
            var rows = data.catalog || [];
            var withPrices = data.show_selling_prices === true;
            return BranchDB.saveCatalog(rows, branchId, {
                show_selling_prices: withPrices,
                commercial_mode: data.commercial_mode || "",
            }).then(function () {
                banner.hidden = true;
                setCatalog(rows, withPrices);
            });
        })
        .catch(function () {
            return loadFromCache();
        });
}());
