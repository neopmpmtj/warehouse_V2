(function () {
    const LANG_KEY = "cc-lang";
    const CSRF = document.querySelector('meta[name="csrf-token"]');
    const CSRF_TOKEN = CSRF ? CSRF.content : "";
    const SIDE = document.body.getAttribute("data-side") || "warehouse";
    const LIST_URL = document.body.getAttribute("data-list-url") || "";
    const MARK_READ_TEMPLATE =
        document.body.getAttribute("data-mark-read-url") || "";

    function safeGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function currentLang() {
        const raw = safeGet(LANG_KEY, "pt");
        return String(raw).toLowerCase().indexOf("en") === 0 ? "en" : "pt";
    }

    function locale() {
        return currentLang() === "pt" ? "pt-PT" : "en-GB";
    }

    function t(key, vars) {
        const dict = ALERTS_I18N[currentLang()] || ALERTS_I18N.en;
        let value = dict[key];
        if (value === undefined) {
            value = ALERTS_I18N.en[key] || key;
        }
        if (vars) {
            Object.keys(vars).forEach(function (name) {
                value = value.replaceAll("{" + name + "}", String(vars[name]));
            });
        }
        return value;
    }

    function applyStaticI18n() {
        document.title = t("title") + " — CentCompras";
        const scope = SIDE === "branch" ? document.querySelector("main") : document;
        if (!scope) {
            return;
        }
        const dict = ALERTS_I18N[currentLang()] || ALERTS_I18N.en;
        scope.querySelectorAll("[data-i18n]").forEach(function (node) {
            const key = node.getAttribute("data-i18n");
            if (key && dict[key] !== undefined) {
                node.textContent = t(key);
            }
        });
        if (SIDE === "warehouse") {
            document.querySelectorAll("header [data-i18n]").forEach(function (node) {
                const key = node.getAttribute("data-i18n");
                if (key && dict[key] !== undefined) {
                    node.textContent = t(key);
                }
            });
        }
    }

    function formatWhen(iso) {
        const date = new Date(iso);
        if (Number.isNaN(date.getTime())) {
            return iso || t("dash");
        }
        return date.toLocaleString(locale(), {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });
    }

    function discrepancyHtml(lines) {
        if (!lines || !lines.length) {
            return t("dash");
        }
        const items = lines.map(function (line) {
            return (
                "<li>" +
                escapeHtml(
                    t("lineDetail", {
                        code: line.internal_code || t("dash"),
                        shipped: line.shipped,
                        received: line.received,
                        missing: line.missing,
                    })
                ) +
                "</li>"
            );
        });
        return '<ul class="alerts-lines">' + items.join("") + "</ul>";
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    }

    function showBanner(message) {
        const banner = document.getElementById("banner");
        if (!banner) {
            return;
        }
        if (!message) {
            banner.hidden = true;
            banner.textContent = "";
            return;
        }
        banner.hidden = false;
        banner.textContent = message;
    }

    function markReadUrl(id) {
        return MARK_READ_TEMPLATE.replace("{id}", String(id));
    }

    function markRead(id, row) {
        return fetch(markReadUrl(id), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": CSRF_TOKEN,
            },
            body: "{}",
            credentials: "same-origin",
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("mark-read");
            }
            row.classList.remove("is-unread");
        });
    }

    function render(alerts) {
        const body = document.getElementById("alerts-body");
        const empty = document.getElementById("alerts-empty");
        if (!body) {
            return;
        }
        body.replaceChildren();
        if (!alerts.length) {
            if (empty) {
                empty.hidden = false;
            }
            return;
        }
        if (empty) {
            empty.hidden = true;
        }
        alerts.forEach(function (alert) {
            const row = document.createElement("tr");
            row.dataset.id = String(alert.id);
            if (alert.unread) {
                row.classList.add("is-unread");
            }
            const followUp =
                alert.follow_up_request_id == null
                    ? t("dash")
                    : "#" + alert.follow_up_request_id;
            const cells = [];
            cells.push(escapeHtml(formatWhen(alert.received_at)));
            if (SIDE === "warehouse") {
                cells.push(escapeHtml(alert.branch_name || t("dash")));
            }
            cells.push("#" + escapeHtml(alert.request_id));
            cells.push("#" + escapeHtml(alert.dispatch_id));
            cells.push(discrepancyHtml(alert.lines));
            cells.push(escapeHtml(alert.reason || t("dash")));
            cells.push(escapeHtml(followUp));
            row.innerHTML = cells.map(function (html) {
                return "<td>" + html + "</td>";
            }).join("");
            row.addEventListener("click", function () {
                markRead(alert.id, row).catch(function () {
                    showBanner(t("markReadError"));
                });
            });
            body.appendChild(row);
        });
    }

    function load() {
        return fetch(LIST_URL, { credentials: "same-origin" })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("list");
                }
                return response.json();
            })
            .then(function (payload) {
                showBanner("");
                render(payload.alerts || []);
            })
            .catch(function () {
                showBanner(t("loadError"));
            });
    }

    applyStaticI18n();
    load();
    window.addEventListener("cc-lang-changed", function () {
        applyStaticI18n();
        load();
    });
})();
