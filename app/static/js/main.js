// =====================================================================
// Toolbox Everything — utilitaires globaux (vanilla JS, pas de bundler)
//
// Source unique des notifications (toasts). Les templates appellent
// `showNotification(message, type)` ou `window.Toolbox.notify(...)`.
// Le style vient de `.toast` dans style.css (piloté par les tokens).
// =====================================================================

const NOTIFICATION_DURATION = 3200;

const TOAST_ICONS = {
    success: "fa-circle-check",
    error: "fa-circle-exclamation",
    info: "fa-circle-info",
    warning: "fa-triangle-exclamation",
};

function ensureToastContainer() {
    let container = document.getElementById("notifications");
    if (!container) {
        container = document.createElement("div");
        container.id = "notifications";
        container.className = "fixed top-4 right-4 z-50 space-y-2";
        document.body.appendChild(container);
    }
    return container;
}

function notify(message, type = "success", duration = NOTIFICATION_DURATION) {
    const container = ensureToastContainer();
    const kind = TOAST_ICONS[type] ? type : "info";

    const toast = document.createElement("div");
    toast.className = `toast toast--${kind}`;
    toast.setAttribute("role", kind === "error" ? "alert" : "status");

    const icon = document.createElement("i");
    icon.className = `toast__icon fas ${TOAST_ICONS[kind]}`;
    icon.setAttribute("aria-hidden", "true");

    const text = document.createElement("span");
    text.textContent = message;

    toast.append(icon, text);
    container.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("is-visible"));

    window.setTimeout(() => {
        toast.classList.remove("is-visible");
        window.setTimeout(() => toast.remove(), 220);
    }, duration);

    return toast;
}

// Compat : ancien nom global utilisé par plusieurs templates.
function showNotification(message, type = "success") {
    return notify(message, type);
}

const handleError = (error) => {
    console.error("Error:", error);
    notify(error?.message || "Une erreur est survenue", "error");
};

const FormUtils = {
    validateEmail: (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email),
    validateURL: (url) => {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },
    serializeForm: (form) => Object.fromEntries(new FormData(form).entries()),
};

const FileUtils = {
    formatFileSize: (bytes) => {
        if (!bytes) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
    },
    isValidFileType: (file, allowedTypes) => allowedTypes.includes(file.type),
};

// API publique.
window.Toolbox = { notify, handleError, FormUtils, FileUtils };
window.showNotification = showNotification;
window.handleError = handleError;
window.FormUtils = FormUtils;
window.FileUtils = FileUtils;
