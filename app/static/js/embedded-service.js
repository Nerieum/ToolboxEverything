function initEmbeddedServices() {
    document.querySelectorAll('[data-service-status]').forEach(async (status) => {
        const label = status.querySelector('.service-status__label');

        try {
            const response = await fetch(status.dataset.serviceStatus, {
                headers: { Accept: 'application/json' },
            });
            const data = await response.json();
            const available = response.ok && data.reachable === true;

            status.dataset.state = available ? 'online' : 'offline';
            if (label) label.textContent = available ? 'Disponible' : 'Indisponible';
        } catch {
            status.dataset.state = 'offline';
            if (label) label.textContent = 'Indisponible';
        }
    });

    document.querySelectorAll('[data-service-frame-shell]').forEach((shell) => {
        const frame = shell.querySelector('[data-service-frame]');
        if (!frame) return;

        const revealFrame = () => shell.classList.add('is-loaded');
        frame.addEventListener('load', revealFrame, { once: true });
        window.setTimeout(revealFrame, 2500);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEmbeddedServices, { once: true });
} else {
    initEmbeddedServices();
}
