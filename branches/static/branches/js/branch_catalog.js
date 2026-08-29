"use strict";

(function () {
    var body = document.getElementById("catalog-body");
    var empty = document.getElementById("empty");
    var banner = document.getElementById("banner");
    var head = document.getElementById("catalog-head");
    if (!body || !banner || !head) {
        return;
    }

    var branchId = document.body.getAttribute("data-branch-id");
    var AVAIL = { none: "None", low: "Low", "in stock": "In stock" };
    var AVAIL_CLASS = { none: "avail-none", low: "avail-low", "in stock": "avail-ok" };

    function cell(text, className) {
        var td = document.createElement("td");
        td.textContent = text == null ? "" : text;
        if (className) {
            td.className = className;
        }
        return td;
    }

    function headerCell(text) {
        var th = document.createElement("th");
        th.textContent = text;
        return th;
    }

    function showSellingPricesFrom(meta) {
        return !!(meta && meta.show_selling_prices === true);
    }

    function renderHead(withPrices) {
        head.textContent = "";
        ["Code", "Description", "Family", "Sub-family", "Unit"].forEach(function (label) {
            head.appendChild(headerCell(label));
        });
        if (withPrices) {
            ["Retail", "Wholesale", "Special"].forEach(function (label) {
                head.appendChild(headerCell(label));
            });
        }
        head.appendChild(headerCell("Availability"));
    }

    function showBanner(message, isInfo) {
        banner.textContent = message;
        banner.hidden = false;
        if (isInfo) {
            banner.style.background = "#e8f0fe";
            banner.style.color = "#0b57d0";
        } else {
            banner.style.background = "#fdecea";
            banner.style.color = "#b00020";
        }
    }

    function render(rows, withPrices) {
        renderHead(withPrices);
        body.textContent = "";
        rows.forEach(function (row) {
            var tr = document.createElement("tr");
            tr.appendChild(cell(row.internal_code));
            tr.appendChild(cell(row.description));
            tr.appendChild(cell(row.family));
            tr.appendChild(cell(row.sub_family));
            tr.appendChild(cell(row.unit_of_measure));
            if (withPrices) {
                tr.appendChild(cell(row.retail_price));
                tr.appendChild(cell(row.wholesale_price));
                tr.appendChild(cell(row.special_price));
            }
            tr.appendChild(cell(AVAIL[row.availability] || row.availability, AVAIL_CLASS[row.availability]));
            body.appendChild(tr);
        });
        empty.hidden = rows.length !== 0;
    }

    function formatLastUpdated(iso) {
        if (!iso) {
            return "unknown time";
        }
        try {
            return new Date(iso).toLocaleString();
        } catch (e) {
            return iso;
        }
    }

    function loadFromCache() {
        return BranchDB.getCachedCatalog().then(function (data) {
            var cache = BranchOffline.catalogCacheForBranch(data, branchId);
            if (!cache.ok) {
                showBanner(cache.message);
                empty.hidden = true;
                return;
            }
            if (!cache.items.length) {
                showBanner("No cached catalogue. Connect to Wi-Fi to download.");
                empty.hidden = true;
                return;
            }
            var withPrices = showSellingPricesFrom(data.meta);
            render(cache.items, withPrices);
            showBanner(
                "Offline — showing last update from " +
                    formatLastUpdated(data.meta && data.meta.last_updated) +
                    ". Availability may be outdated.",
                true
            );
        });
    }

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
                render(rows, withPrices);
            });
        })
        .catch(function () {
            return loadFromCache();
        });
}());
