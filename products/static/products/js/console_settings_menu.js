(function () {
    function bindSettingsMenu() {
        const toggle = document.getElementById("settings-toggle");
        const popover = document.getElementById("settings-popover");
        if (!toggle || !popover) {
            return;
        }

        function setOpen(open) {
            popover.hidden = !open;
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        }

        toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            setOpen(popover.hidden);
        });
        document.addEventListener("click", (event) => {
            if (popover.hidden) {
                return;
            }
            if (popover.contains(event.target) || toggle.contains(event.target)) {
                return;
            }
            setOpen(false);
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !popover.hidden) {
                event.preventDefault();
                event.stopImmediatePropagation();
                setOpen(false);
                toggle.focus();
            }
        });
    }

    const HELP_I18N = {
        en: {
            help: "Help",
            close: "Close",
            manualUnavailable: "Manual not available.",
        },
        pt: {
            help: "Ajuda",
            close: "Fechar",
            manualUnavailable: "Manual indisponível.",
        },
    };

    function currentHelpLang() {
        let lang = "en";
        try {
            lang = localStorage.getItem("cc-lang") || "en";
        } catch (_) {
            /* ignore */
        }
        if (String(lang).toLowerCase().startsWith("pt")) {
            return "pt";
        }
        return "en";
    }

    function helpT(key) {
        const lang = currentHelpLang();
        return (HELP_I18N[lang] && HELP_I18N[lang][key]) || HELP_I18N.en[key] || key;
    }

    function updateHelpHref() {
        const help = document.getElementById("settings-help");
        if (!help) {
            return;
        }
        const slug = help.getAttribute("data-help-slug") || "01-items";
        help.setAttribute("href", manualUrl(currentHelpLang(), slug, "pdf"));
    }

    function manualUrl(lang, slug, ext) {
        return "/docs/user-manuals/" + lang + "/" + slug + "." + ext;
    }

    function bindHelpLauncher() {
        const help = document.getElementById("settings-help");
        if (!help) {
            return;
        }
        const slug = help.getAttribute("data-help-slug") || "01-items";
        help.addEventListener("click", (event) => {
            event.preventDefault();
            openHelp(slug);
        });
    }

    async function openHelp(slug) {
        const lang = currentHelpLang();
        // 1) Try the .pdf in the current language, then English — open in the browser when present.
        for (const candidate of [lang, "en"]) {
            const pdfUrl = manualUrl(candidate, slug, "pdf");
            try {
                const res = await fetch(pdfUrl, { method: "HEAD", credentials: "same-origin" });
                if (res.ok) {
                    window.open(pdfUrl, "_blank", "noopener");
                    return;
                }
            } catch (_) {
                /* fall through to next candidate */
            }
        }
        // 2) PDF missing/unreachable — show the .md in a popover (current lang, then English).
        for (const candidate of [lang, "en"]) {
            const mdUrl = manualUrl(candidate, slug, "md");
            try {
                const res = await fetch(mdUrl, { credentials: "same-origin" });
                if (res.ok) {
                    showHelpPopover(await res.text());
                    return;
                }
            } catch (_) {
                /* fall through to next candidate */
            }
        }
        showHelpPopover(null);
    }

    function showHelpPopover(mdText) {
        const existing = document.getElementById("help-popover");
        if (existing) {
            existing.remove();
        }
        const overlay = document.createElement("div");
        overlay.id = "help-popover";
        overlay.className = "help-popover-overlay";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-label", "Help");

        const panel = document.createElement("div");
        panel.className = "help-popover";

        const head = document.createElement("div");
        head.className = "help-popover-head";
        const title = document.createElement("span");
        title.className = "help-popover-title";
        title.textContent = helpT("help");
        const close = document.createElement("button");
        close.type = "button";
        close.className = "help-popover-close";
        close.setAttribute("aria-label", helpT("close"));
        close.textContent = "×";
        head.appendChild(title);
        head.appendChild(close);

        const body = document.createElement("pre");
        body.className = "help-popover-body";
        body.textContent = mdText ?? helpT("manualUnavailable");

        panel.appendChild(head);
        panel.appendChild(body);
        overlay.appendChild(panel);
        document.body.appendChild(overlay);

        function closePopover() {
            overlay.remove();
            document.removeEventListener("keydown", onKeydown);
        }
        function onKeydown(event) {
            if (event.key === "Escape") {
                closePopover();
            }
        }
        close.addEventListener("click", closePopover);
        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                closePopover();
            }
        });
        document.addEventListener("keydown", onKeydown);
    }

    function bindAll() {
        bindSettingsMenu();
        bindHelpLauncher();
        updateHelpHref();
        window.addEventListener("storage", (event) => {
            if (event.key === "cc-lang") {
                updateHelpHref();
            }
        });
        document.addEventListener("cc-lang-changed", updateHelpHref);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindAll);
    } else {
        bindAll();
    }
})();
