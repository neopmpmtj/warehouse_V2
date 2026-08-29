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
            signOutOtherDevices: "Sign out other devices",
            help: "Help",
            dashTitle: "Dashboard — CentCompras",
            groupsLabel: "Groups:",
            groupsNone: "none",
            sectionCompanyVoice: "Company Voice",
            cardCompanyVoice: "Company Voice",
            cardCompanyVoiceDesc:
                "Suggestions, praise, and concerns — all logged-in staff can read and post.",
            sectionWarehouse: "Warehouse pages",
            cardItemConsole: "Item console",
            cardItemConsoleDesc:
                "Manage the catalogue: items, families, sub-families, suppliers, prices",
            cardManagerCatalog: "Manager catalog",
            cardManagerCatalogDesc: "Stock + price view across the whole catalogue",
            cardCostTrends: "Cost trends",
            cardCostTrendsDesc: "Reference purchase cost over time (demo chart)",
            cardPurchaseOrders: "Purchase orders",
            cardPurchaseOrdersDesc:
                "Create, approve, receive and manage purchase orders",
            cardGoodsReceipts: "Goods receipts & stock",
            cardGoodsReceiptsDesc: "Receive goods, adjust stock, view stock movements",
            cardInternalRequests: "Internal requests",
            cardInternalRequestsDesc:
                "Warehouse queue: fulfil branch requisições and issue goods",
            cardRequestThreads: "Request threads",
            cardRequestThreadsDesc: "Catalogue-gap requests from branches",
            cardPoLimits: "PO approval limits",
            cardPoLimitsDesc: "Warehouse approval caps (admins only)",
            cardBranchLimits: "Branch approval limits",
            cardBranchLimitsDesc: "Branch manager caps (admins only)",
            cardDjangoAdmin: "Django admin",
            cardDjangoAdminDesc: "Site administration (superuser only)",
            sectionVisualizations: "Visualizations",
            visualizationsNote:
                "Charts and trends for analysis — not day-to-day operations.",
            sectionBranch: "Branch pages",
            branchNote:
                "These need a branch membership. Warehouse-only logins are sent to the picker or refused.",
            cardBranchPicker: "Branch picker",
            cardBranchPickerDesc: "Switch the active branch",
            cardBranchCatalog: "Branch catalog",
            cardBranchCatalogDesc:
                "Read-only catalogue (cost always hidden; selling prices only in priced mode)",
            cardRequisicao: "Requisição interna",
            cardRequisicaoDesc: "Request stock from the warehouse",
            cardBranchThreads: "Branch threads",
            cardBranchThreadsDesc: "Request items not in the catalogue",
            cardBranchReceipts: "Branch receipts",
            cardBranchReceiptsDesc: "Receive goods and view branch stock",
            branchEyebrow: "CentCompras",
            branchDashTitle: "Dashboard",
            sectionBranchWork: "Your branch",
            branchRoleLabel: "Role:",
            navBranchHome: "Home",
            navBranchCatalog: "Catalog",
            navBranchRequests: "Requests",
            navBranchThreads: "Threads",
            navBranchReceipts: "Receipts",
            switchBranch: "Switch branch",
            navWarehouseHome: "Home",
            navWarehouseItems: "Items",
            navWarehouseCatalog: "Catalog",
            navWarehousePOs: "POs",
            navWarehouseReceipts: "Receipts",
            navWarehouseRequests: "Requests",
            navWarehouseThreads: "Threads",
            devReference: "Developer reference — permissions, auth & APIs",
        },
        pt: {
            language: "Idioma",
            themeDark: "Tema escuro",
            themeLight: "Tema claro",
            settings: "Definições",
            settingsAria: "Definições",
            signedInAs: "Sessão iniciada como",
            signOut: "Terminar sessão",
            signOutOtherDevices: "Terminar sessão noutros dispositivos",
            help: "Ajuda",
            dashTitle: "Painel — CentCompras",
            groupsLabel: "Grupos:",
            groupsNone: "nenhum",
            sectionCompanyVoice: "Voz da Empresa",
            cardCompanyVoice: "Voz da Empresa",
            cardCompanyVoiceDesc:
                "Sugestões, elogios e preocupações — todos os colaboradores autenticados podem ler e publicar.",
            sectionWarehouse: "Páginas do armazém",
            cardItemConsole: "Gestão de artigos",
            cardItemConsoleDesc:
                "Gerir o catálogo: artigos, famílias, sub-famílias, fornecedores, preços",
            cardManagerCatalog: "Catálogo do gestor",
            cardManagerCatalogDesc: "Vista de stock e preços de todo o catálogo",
            cardCostTrends: "Evolução de custos",
            cardCostTrendsDesc: "Custo de compra de referência ao longo do tempo (gráfico demo)",
            cardPurchaseOrders: "Encomendas de compra",
            cardPurchaseOrdersDesc:
                "Criar, aprovar, receber e gerir encomendas de compra",
            cardGoodsReceipts: "Receção de mercadorias e stock",
            cardGoodsReceiptsDesc:
                "Receber mercadoria, ajustar stock, ver movimentos de stock",
            cardInternalRequests: "Pedidos internos",
            cardInternalRequestsDesc:
                "Fila do armazém: cumprir requisições das filiais e emitir mercadoria",
            cardRequestThreads: "Fios de pedido",
            cardRequestThreadsDesc: "Pedidos de artigos que não estão no catálogo",
            cardPoLimits: "Limites de aprovação de encomendas",
            cardPoLimitsDesc: "Tetos de aprovação do armazém (só administradores)",
            cardBranchLimits: "Limites de aprovação das filiais",
            cardBranchLimitsDesc: "Tetos dos gestores de filial (só administradores)",
            cardDjangoAdmin: "Administração Django",
            cardDjangoAdminDesc: "Administração do sítio (só superutilizador)",
            sectionVisualizations: "Visualizações",
            visualizationsNote:
                "Gráficos e tendências para análise — não operações do dia a dia.",
            sectionBranch: "Páginas da filial",
            branchNote:
                "Requerem uma adesão à filial. Inícios de sessão só de armazém são enviados ao seletor ou recusados.",
            cardBranchPicker: "Seletor de filial",
            cardBranchPickerDesc: "Mudar a filial ativa",
            cardBranchCatalog: "Catálogo da filial",
            cardBranchCatalogDesc:
                "Catálogo só de leitura (custo sempre oculto; preços de venda só no modo com preços)",
            cardRequisicao: "Requisição interna",
            cardRequisicaoDesc: "Pedir stock ao armazém",
            cardBranchThreads: "Fios da filial",
            cardBranchThreadsDesc: "Pedir artigos que não estão no catálogo",
            cardBranchReceipts: "Receções da filial",
            cardBranchReceiptsDesc: "Receber mercadoria e ver o stock da filial",
            branchEyebrow: "CentCompras",
            branchDashTitle: "Painel",
            sectionBranchWork: "A sua filial",
            branchRoleLabel: "Função:",
            navBranchHome: "Início",
            navBranchCatalog: "Catálogo",
            navBranchRequests: "Pedidos",
            navBranchThreads: "Fios",
            navBranchReceipts: "Receções",
            switchBranch: "Mudar filial",
            navWarehouseHome: "Início",
            navWarehouseItems: "Artigos",
            navWarehouseCatalog: "Catálogo",
            navWarehousePOs: "Encomendas",
            navWarehouseReceipts: "Receções",
            navWarehouseRequests: "Pedidos",
            navWarehouseThreads: "Fios",
            devReference: "Referência para programadores — permissões, autenticação e APIs",
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
        if (document.querySelector(".dash-main") && DICT[lang] && DICT[lang].dashTitle) {
            document.title = DICT[lang].dashTitle;
        }
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
                document.dispatchEvent(new CustomEvent("cc-lang-changed"));
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
