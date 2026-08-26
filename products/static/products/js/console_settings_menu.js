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

    function bindHelpLauncher() {
        const help = document.getElementById("settings-help");
        if (!help) {
            return;
        }
        const pdfUrl = help.getAttribute("href");
        const mdUrl = help.getAttribute("data-help-md");
        if (!pdfUrl || !mdUrl) {
            return;
        }
        help.addEventListener("click", (event) => {
            event.preventDefault();
            openHelp(pdfUrl, mdUrl);
        });
    }

    async function openHelp(pdfUrl, mdUrl) {
        // 1) Try the .pdf first — open it in the browser when present.
        try {
            const res = await fetch(pdfUrl, { method: "HEAD", credentials: "same-origin" });
            if (res.ok) {
                window.open(pdfUrl, "_blank", "noopener");
                return;
            }
        } catch (_) {
            /* fall through to .md */
        }
        // 2) PDF missing/unreachable — show the .md in a popover instead.
        try {
            const res = await fetch(mdUrl, { credentials: "same-origin" });
            if (res.ok) {
                showHelpPopover(await res.text());
                return;
            }
        } catch (_) {
            /* fall through */
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
        title.textContent = "Help";
        const close = document.createElement("button");
        close.type = "button";
        close.className = "help-popover-close";
        close.setAttribute("aria-label", "Close");
        close.textContent = "×";
        head.appendChild(title);
        head.appendChild(close);

        const body = document.createElement("pre");
        body.className = "help-popover-body";
        body.textContent = mdText ?? "Manual not available.";

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
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindAll);
    } else {
        bindAll();
    }
})();
