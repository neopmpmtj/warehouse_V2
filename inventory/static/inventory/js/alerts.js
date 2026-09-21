(function () {
    const LANG_KEY = "cc-lang";
    const CSRF = document.querySelector('meta[name="csrf-token"]');
    const CSRF_TOKEN = CSRF ? CSRF.content : "";
    const SIDE = document.body.getAttribute("data-side") || "warehouse";
    const LIST_URL = document.body.getAttribute("data-list-url") || "";
    const MARK_READ_TEMPLATE =
        document.body.getAttribute("data-mark-read-url") || "";
    const EVENT_MARK_READ_TEMPLATE =
        document.body.getAttribute("data-event-mark-read-url") || "";

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

    function markReadUrl(alert) {
        const kind = alert.kind || "discrepancy";
        if (kind !== "discrepancy" && EVENT_MARK_READ_TEMPLATE) {
            return EVENT_MARK_READ_TEMPLATE.replace("{id}", String(alert.id));
        }
        return MARK_READ_TEMPLATE.replace("{id}", String(alert.id));
    }

    function markRead(alert, card) {
        if (!card.classList.contains("is-unread") || card.dataset.marking === "1") {
            return Promise.resolve();
        }
        card.dataset.marking = "1";
        return fetch(markReadUrl(alert), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": CSRF_TOKEN,
            },
            body: "{}",
            credentials: "same-origin",
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("mark-read");
                }
                card.classList.remove("is-unread");
            })
            .finally(function () {
                delete card.dataset.marking;
            });
    }

    function metaRow(label, valueHtml) {
        return (
            '<div class="alert-field">' +
            "<dt>" +
            escapeHtml(label) +
            "</dt>" +
            "<dd>" +
            valueHtml +
            "</dd>" +
            "</div>"
        );
    }

    function returnLinesHtml(kind, lines) {
        if (!lines || !lines.length) {
            return t("dash");
        }
        const key =
            kind === "dispatch_return_written_off" ? "writeOffLine" : "restockLine";
        const items = lines.map(function (line) {
            return (
                "<li>" +
                escapeHtml(
                    t(key, {
                        code: line.internal_code || t("dash"),
                        qty: line.quantity,
                    })
                ) +
                "</li>"
            );
        });
        return '<ul class="alerts-lines">' + items.join("") + "</ul>";
    }

    function moreHtml(alert) {
        const reorderValue = alert.reorder ? t("reorderTrue") : t("reorderFalse");
        let html =
            '<p class="alert-reorder">' +
            escapeHtml(t("reorder")) +
            ": " +
            escapeHtml(reorderValue) +
            "</p>";
        if (!alert.reorder) {
            return html;
        }
        const followId =
            alert.follow_up_request_id == null
                ? t("dash")
                : String(alert.follow_up_request_id);
        html +=
            '<p class="alert-follow-up">' +
            escapeHtml(t("followUpRequest", { id: followId })) +
            "</p>";
        const followLines = alert.follow_up_lines || [];
        if (followLines.length) {
            const items = followLines.map(function (line) {
                return (
                    "<li>" +
                    escapeHtml(
                        t("followUpLine", {
                            code: line.internal_code || t("dash"),
                            qty: line.quantity,
                        })
                    ) +
                    "</li>"
                );
            });
            html += '<ul class="alerts-lines">' + items.join("") + "</ul>";
        }
        return html;
    }

    function render(alerts) {
        const list = document.getElementById("alerts-list");
        const empty = document.getElementById("alerts-empty");
        if (!list) {
            return;
        }
        list.replaceChildren();
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
            const card = document.createElement("article");
            const kind = alert.kind || "discrepancy";
            card.className = "alert-card";
            card.dataset.id = String(alert.id);
            card.dataset.kind = kind;
            if (alert.unread) {
                card.classList.add("is-unread");
            }
            const fields = [];
            fields.push(metaRow(t("colWhen"), escapeHtml(formatWhen(alert.received_at))));
            if (SIDE === "warehouse") {
                fields.push(
                    metaRow(t("colBranch"), escapeHtml(alert.branch_name || t("dash")))
                );
            }
            fields.push(metaRow(t("colRequest"), "#" + escapeHtml(alert.request_id)));
            fields.push(metaRow(t("colDispatch"), "#" + escapeHtml(alert.dispatch_id)));
            if (kind !== "discrepancy") {
                fields.push(
                    metaRow(
                        t("colReturn"),
                        "#" + escapeHtml(alert.dispatch_return_id || t("dash"))
                    )
                );
            }
            if (kind === "discrepancy") {
                fields.push(metaRow(t("colDiscrepancy"), discrepancyHtml(alert.lines)));
                fields.push(metaRow(t("colReason"), escapeHtml(alert.reason || t("dash"))));
            } else if (kind === "dispatch_return_opened") {
                /* identifiers only — no SKU or qty */
            } else if (kind === "dispatch_return_restocked") {
                fields.push(
                    metaRow(t("kind_dispatch_return_restocked"), returnLinesHtml(kind, alert.lines))
                );
            } else if (kind === "dispatch_return_written_off") {
                fields.push(
                    metaRow(t("kind_dispatch_return_written_off"), returnLinesHtml(kind, alert.lines))
                );
                fields.push(metaRow(t("colReason"), escapeHtml(alert.reason || t("dash"))));
            }
            let extra = "";
            if (kind === "discrepancy") {
                extra =
                    '<details class="alert-more">' +
                    "<summary>" +
                    escapeHtml(t("seeMore")) +
                    "</summary>" +
                    '<div class="alert-more-body">' +
                    moreHtml(alert) +
                    "</div>" +
                    "</details>";
            }
            card.innerHTML =
                '<h2 class="alert-kind">' +
                escapeHtml(t("kind_" + kind)) +
                "</h2>" +
                '<dl class="alert-fields">' +
                fields.join("") +
                "</dl>" +
                extra;
            const details = card.querySelector("details");
            const summary = card.querySelector("summary");
            if (details && summary) {
                details.addEventListener("toggle", function () {
                    summary.textContent = details.open ? t("seeLess") : t("seeMore");
                });
            }
            card.addEventListener("click", function () {
                markRead(alert, card).catch(function () {
                    showBanner(t("markReadError"));
                });
            });
            list.appendChild(card);
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
