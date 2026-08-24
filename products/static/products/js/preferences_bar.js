/* Centralized language + theme preferences bar (landing dashboards).

   Reads/writes the same localStorage keys the consoles use (cc-lang /
   cc-theme), so a choice made here is already applied when the user
   navigates to any console page.

   Language codes: the dashboard <select> stores "en" / "pt". Warehouse
   console dictionaries were keyed as "pt-PT" (the old Settings popover
   value). Normalize so both stored values apply.
*/
(function () {
    const LANG_KEY = "cc-lang";
    const THEME_KEY = "cc-theme";

    const DICT = {
        en: {
            language: "Language",
            themeDark: "Dark theme",
            themeLight: "Light theme",
            settings: "Settings",
            settingsAria: "Settings",
            signedInAs: "Signed in as",
            signOut: "Sign out",
            help: "Help",
        },
        pt: {
            language: "Idioma",
            themeDark: "Tema escuro",
            themeLight: "Tema claro",
            settings: "Definições",
            settingsAria: "Definições",
            signedInAs: "Sessão iniciada como",
            signOut: "Terminar sessão",
            help: "Ajuda",
        },
    };

    function safeGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function safeSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            /* ignore */
        }
    }

    function normalizeLang(raw) {
        if (raw && String(raw).toLowerCase().startsWith("pt")) {
            return "pt";
        }
        return "en";
    }

    function currentLang() {
        return normalizeLang(safeGet(LANG_KEY, "en"));
    }

    function currentTheme() {
        return safeGet(THEME_KEY, "light");
    }

    function t(key) {
        const dict = DICT[currentLang()] || DICT.en;
        return dict[key] || key;
    }

    function applyStaticI18n() {
        const lang = currentLang();
        document.documentElement.lang = lang === "pt" ? "pt-PT" : "en";
        document.querySelectorAll("[data-i18n]").forEach((node) => {
            const key = node.getAttribute("data-i18n");
            if (DICT[lang] && DICT[lang][key]) {
                node.textContent = t(key);
            }
        });
        document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
            const key = node.getAttribute("data-i18n-aria");
            if (DICT[lang] && DICT[lang][key]) {
                node.setAttribute("aria-label", t(key));
            }
        });
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        const button = document.getElementById("pref-theme");
        if (button) {
            button.textContent = theme === "dark" ? t("themeLight") : t("themeDark");
            button.setAttribute("aria-label", theme === "dark" ? t("themeLight") : t("themeDark"));
        }
    }

    function bind() {
        const canonical = currentLang();
        if (safeGet(LANG_KEY, "en") !== canonical) {
            safeSet(LANG_KEY, canonical);
        }
        const select = document.getElementById("pref-language");
        if (select) {
            select.value = canonical;
            select.addEventListener("change", (event) => {
                safeSet(LANG_KEY, normalizeLang(event.target.value));
                applyStaticI18n();
                applyTheme(currentTheme());
            });
        }
        const button = document.getElementById("pref-theme");
        if (button) {
            button.addEventListener("click", () => {
                const next = currentTheme() === "dark" ? "light" : "dark";
                safeSet(THEME_KEY, next);
                applyTheme(next);
            });
        }
        applyStaticI18n();
        applyTheme(currentTheme());
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bind);
    } else {
        bind();
    }
})();
