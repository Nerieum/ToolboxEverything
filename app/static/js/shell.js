// Interactions du shell global : thème, menu compact et sous-menu mobile.
document.addEventListener("DOMContentLoaded", () => {
    window.requestAnimationFrame(() => document.body.classList.add("loaded"));

    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");
    const mobileMenuBtn = document.getElementById("mobileMenuBtn");
    const mobileMenu = document.getElementById("mobileMenu");
    const mobileMenuBackdrop = document.getElementById("mobileMenuBackdrop");
    let mobileMenuHideTimer = null;

    const storeTheme = (theme) => {
        try {
            localStorage.setItem("theme", theme);
        } catch {
            // Le thème reste actif pour la session si le stockage est indisponible.
        }
    };

    const syncThemeControls = (isDark) => {
        themeToggle?.setAttribute("aria-pressed", String(isDark));
        themeToggle?.setAttribute(
            "title",
            isDark ? "Passer en mode clair" : "Passer en mode sombre",
        );
    };

    const setTheme = (theme) => {
        const isDark = theme === "dark";
        const background = isDark ? "#0e0f13" : "#f3f3f0";
        root.classList.toggle("dark", isDark);
        root.style.backgroundColor = background;
        document.querySelector('meta[name="theme-color"]')?.setAttribute("content", background);
        syncThemeControls(isDark);
        storeTheme(theme);
    };

    syncThemeControls(root.classList.contains("dark"));
    themeToggle?.addEventListener("click", () => {
        setTheme(root.classList.contains("dark") ? "light" : "dark");
    });

    const openMobileMenu = () => {
        if (!mobileMenu) return;
        window.clearTimeout(mobileMenuHideTimer);
        mobileMenu.classList.remove("hidden");
        mobileMenu.setAttribute("aria-hidden", "false");
        document.body.classList.add("mobile-menu-open");
        mobileMenuBtn?.setAttribute("aria-expanded", "true");
        window.requestAnimationFrame(() => mobileMenu.classList.add("is-open"));
    };

    const closeMobileMenu = (immediate = false) => {
        if (!mobileMenu || mobileMenu.classList.contains("hidden")) return;
        mobileMenu.classList.remove("is-open");
        mobileMenu.setAttribute("aria-hidden", "true");
        document.body.classList.remove("mobile-menu-open");
        mobileMenuBtn?.setAttribute("aria-expanded", "false");
        window.clearTimeout(mobileMenuHideTimer);

        if (immediate) {
            mobileMenu.classList.add("hidden");
        } else {
            mobileMenuHideTimer = window.setTimeout(
                () => mobileMenu.classList.add("hidden"),
                180,
            );
        }
    };

    mobileMenuBtn?.addEventListener("click", () => {
        if (mobileMenu?.classList.contains("hidden")) openMobileMenu();
        else closeMobileMenu();
    });
    mobileMenuBackdrop?.addEventListener("click", () => closeMobileMenu());
    document.querySelectorAll("[data-close-mobile-menu]").forEach((link) => {
        link.addEventListener("click", () => closeMobileMenu(true));
    });

    document.querySelectorAll("[data-mobile-submenu-toggle]").forEach((button) => {
        button.addEventListener("click", () => {
            const id = button.dataset.mobileSubmenuToggle;
            const submenu = document.getElementById(`${id}-submenu`);
            const chevron = document.getElementById(`${id}-chevron`);
            if (!submenu) return;
            submenu.classList.toggle("hidden");
            const isExpanded = !submenu.classList.contains("hidden");
            chevron?.classList.toggle("rotate-180", isExpanded);
            button.setAttribute("aria-expanded", String(isExpanded));
        });
    });

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMobileMenu();
    });
    window.addEventListener("resize", () => {
        if (window.innerWidth >= 1180) closeMobileMenu(true);
    });
});
