/**
 * Downloader (video/audio), UI client.
 *
 * - détecte la plateforme (YouTube, Vimeo, Dailymotion, TikTok) à la volée
 * - affiche un mini-historique localStorage (5 dernières URLs validées,
 *   jamais envoyées au serveur)
 * - met à jour un compteur de quota à partir des headers `X-RateLimit-*`
 *   renvoyés par Flask-Limiter sur /downloader/info
 *
 * Le serveur a une whitelist stricte côté `_is_allowed_url`. La détection
 * côté client n'a d'autre but que d'améliorer le feedback visuel.
 */

(function () {
    'use strict';

    const HISTORY_KEY = 'toolbox.downloader.history.v1';
    const HISTORY_MAX = 5;

    /** Tableau ordonné : essais de matchers du plus spécifique au plus générique. */
    const PLATFORMS = [
        {
            id: 'youtube',
            label: 'YouTube',
            icon: 'fa-brands fa-youtube',
            color: '#dc2626',
            test: (host) => /(?:^|\.)(youtube\.com|youtu\.be)$/i.test(host),
        },
        {
            id: 'vimeo',
            label: 'Vimeo',
            icon: 'fa-brands fa-vimeo-v',
            color: '#0ea5e9',
            test: (host) => /(?:^|\.)vimeo\.com$/i.test(host),
        },
        {
            id: 'dailymotion',
            label: 'Dailymotion',
            icon: 'fa-solid fa-circle-play',
            color: '#2563eb',
            test: (host) => /(?:^|\.)(dailymotion\.com|dai\.ly)$/i.test(host),
        },
        {
            id: 'tiktok',
            label: 'TikTok',
            icon: 'fa-brands fa-tiktok',
            color: '#0f172a',
            test: (host) => /(?:^|\.)tiktok\.com$/i.test(host),
        },
    ];

    const NEUTRAL = {
        id: null,
        label: 'En attente d\u2019un lien\u2026',
        icon: 'fa-solid fa-link',
        color: '',
    };

    const els = {
        form: document.getElementById('urlForm'),
        urlInput: document.querySelector('[data-dl-input]'),
        inputIcon: document.querySelector('[data-dl-input-icon]'),
        platformPill: document.querySelector('[data-dl-platform-pill]'),
        platformLabel: document.querySelector('[data-dl-platform-label]'),
        platformIcon: document.querySelector('[data-dl-platform-icon]'),
        quotaWrap: document.querySelector('[data-dl-quota]'),
        quotaText: document.querySelector('[data-dl-quota-text]'),
        accent: document.querySelector('.dl-accent'),
        historyWrap: document.querySelector('[data-dl-history]'),
        historyList: document.querySelector('[data-dl-history-list]'),
        historyClear: document.querySelector('[data-dl-history-clear]'),
        loading: document.getElementById('videoLoading'),
        preview: document.getElementById('videoPreview'),
        thumbnail: document.getElementById('thumbnail'),
        title: document.getElementById('videoTitle'),
        channel: document.getElementById('channelName'),
        duration: document.getElementById('videoDuration'),
        views: document.getElementById('videoViews'),
        progressOverlay: document.getElementById('progressOverlay'),
        progressBar: document.getElementById('progressBar'),
        progressText: document.getElementById('progressText'),
        cancelButton: document.getElementById('cancelButton'),
        platformTints: document.querySelectorAll('[data-dl-platform-tint], [data-dl-platform-cta]'),
    };

    let abortController = null;

    // ───────────────────────────── plateforme ─────────────────────────────

    function detectPlatform(rawUrl) {
        if (!rawUrl) return null;
        let u;
        try {
            u = new URL(rawUrl);
        } catch (_e) {
            return null;
        }
        if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
        const host = u.hostname.toLowerCase().replace(/^\./, '');
        return PLATFORMS.find((p) => p.test(host)) || null;
    }

    function applyPlatform(platform) {
        const p = platform || NEUTRAL;
        const root = document.body;

        for (const klass of Array.from(root.classList)) {
            if (klass.startsWith('dl-platform--')) root.classList.remove(klass);
        }
        if (p.id) root.classList.add(`dl-platform--${p.id}`);

        if (els.platformLabel) {
            els.platformLabel.textContent = p.label;
        }
        if (els.platformIcon) {
            els.platformIcon.className = `${p.icon} text-[10px] opacity-80`;
        }
        if (els.platformPill) {
            els.platformPill.style.color = p.color || '';
            els.platformPill.style.borderColor = p.color ? `${p.color}55` : '';
        }
        if (els.inputIcon) {
            els.inputIcon.className = `dl-input-icon ${p.id ? p.icon : 'fa-solid fa-link'}`;
            if (p.id) els.inputIcon.style.color = p.color;
            else els.inputIcon.style.color = '';
        }
        if (els.accent) {
            els.accent.style.color = p.color || '';
        }

        // Boutons CTA : réutilise la couleur de la plateforme si on en a une.
        els.platformTints.forEach((node) => {
            node.style.setProperty('--dl-platform-color', p.color || '');
        });
    }

    // ───────────────────────────── historique ─────────────────────────────

    function loadHistory() {
        try {
            const raw = localStorage.getItem(HISTORY_KEY);
            if (!raw) return [];
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed.slice(0, HISTORY_MAX) : [];
        } catch (_e) {
            return [];
        }
    }

    function saveHistory(entries) {
        try {
            localStorage.setItem(
                HISTORY_KEY,
                JSON.stringify(entries.slice(0, HISTORY_MAX))
            );
        } catch (_e) {
            /* quota plein, on ignore */
        }
    }

    function pushHistory(entry) {
        const existing = loadHistory().filter((e) => e.url !== entry.url);
        existing.unshift(entry);
        saveHistory(existing);
        renderHistory();
    }

    function renderHistory() {
        const entries = loadHistory();
        if (!els.historyWrap || !els.historyList) return;
        if (!entries.length) {
            els.historyWrap.hidden = true;
            els.historyList.innerHTML = '';
            return;
        }
        els.historyWrap.hidden = false;
        els.historyList.innerHTML = '';
        for (const entry of entries) {
            const li = document.createElement('li');
            li.className = 'dl-history__item';
            const platform = detectPlatform(entry.url);
            const iconClass = platform ? platform.icon : 'fa-solid fa-link';
            const color = platform ? platform.color : '';
            li.innerHTML = `
                <button type="button" class="dl-history__btn" title="${escapeHtml(entry.url)}">
                    <i class="${iconClass} text-[11px]" style="color:${color}"></i>
                    <span class="dl-history__label">${escapeHtml(entry.title || entry.url)}</span>
                </button>
            `;
            li.querySelector('button').addEventListener('click', () => {
                els.urlInput.value = entry.url;
                els.urlInput.dispatchEvent(new Event('input', { bubbles: true }));
                els.urlInput.focus();
            });
            els.historyList.appendChild(li);
        }
    }

    function clearHistory() {
        try {
            localStorage.removeItem(HISTORY_KEY);
        } catch (_e) { /* */ }
        renderHistory();
    }

    function escapeHtml(value) {
        return String(value).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }

    // ───────────────────────────── quota ──────────────────────────────────

    function updateQuotaFromResponse(response) {
        if (!els.quotaWrap || !els.quotaText) return;
        const remaining = response.headers.get('X-RateLimit-Remaining');
        const limit = response.headers.get('X-RateLimit-Limit');
        if (!remaining) {
            els.quotaWrap.hidden = true;
            return;
        }
        const remNum = Number(remaining);
        if (Number.isNaN(remNum)) {
            els.quotaWrap.hidden = true;
            return;
        }
        els.quotaWrap.hidden = false;
        if (limit) {
            els.quotaText.textContent = `${remNum}/${limit} requêtes restantes`;
        } else {
            els.quotaText.textContent = `${remNum} requêtes restantes`;
        }
        els.quotaWrap.classList.toggle('dl-status__quota--warn', remNum <= 3);
    }

    // ───────────────────────────── helpers ────────────────────────────────

    function showLoading(isLoading) {
        if (!els.loading) return;
        els.loading.classList.toggle('hidden', !isLoading);
        if (isLoading && els.preview) els.preview.classList.add('hidden');
    }

    function formatDuration(seconds) {
        const total = Number(seconds) || 0;
        const h = Math.floor(total / 3600);
        const m = Math.floor((total % 3600) / 60);
        const s = Math.floor(total % 60);
        const parts = [m.toString().padStart(2, '0'), s.toString().padStart(2, '0')];
        if (h > 0) parts.unshift(String(h));
        return parts.join(':');
    }

    function formatNumber(num) {
        return new Intl.NumberFormat('fr-FR').format(Number(num) || 0);
    }

    function notify(message, type = 'error') {
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        } else {
            console.warn(`[downloader] ${type}: ${message}`);
        }
    }

    // ───────────────────────────── flux principaux ────────────────────────

    async function handleAnalyze(event) {
        event.preventDefault();
        const url = els.urlInput.value.trim();
        if (!url) return;

        const platform = detectPlatform(url);
        if (!platform) {
            notify(
                'URL non supportée sur cette instance. Plateformes acceptées : ' +
                'YouTube, Vimeo, Dailymotion, TikTok.',
                'error'
            );
            return;
        }

        showLoading(true);
        try {
            const response = await fetch(
                `/downloader/info?url=${encodeURIComponent(url)}`
            );
            updateQuotaFromResponse(response);

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Impossible d\u2019analyser cette URL.');
            }

            els.thumbnail.src = data.thumbnail || '';
            els.title.textContent = data.title || '';
            els.channel.querySelector('span').textContent = `Source : ${data.channel}`;
            els.duration.querySelector('span').textContent = `Durée : ${formatDuration(data.duration)}`;
            els.views.querySelector('span').textContent = `Vues : ${formatNumber(data.views)}`;

            showLoading(false);
            els.preview.classList.remove('hidden');

            pushHistory({
                url,
                title: data.title || url,
                platform: platform.id,
                ts: Date.now(),
            });
        } catch (err) {
            showLoading(false);
            notify(err.message || 'Erreur réseau.', 'error');
        }
    }

    async function handleDownload(format) {
        const url = els.urlInput.value.trim();
        if (!url) {
            notify('Saisissez d\u2019abord une URL valide.', 'error');
            return;
        }

        const quality =
            format === 'video'
                ? document.getElementById('videoQuality').value
                : 'highest';

        abortController = new AbortController();
        els.progressOverlay.classList.remove('hidden');
        els.progressBar.style.width = '0%';
        els.progressText.textContent = 'Démarrage du téléchargement';

        try {
            const response = await fetch('/downloader/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, format, quality }),
                signal: abortController.signal,
            });
            updateQuotaFromResponse(response);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'Téléchargement impossible.');
            }

            els.progressText.textContent = 'Réception du fichier';
            els.progressBar.style.width = '60%';

            const blob = await response.blob();
            const downloadUrl = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = filenameFrom(response.headers.get('content-disposition')) || 'download';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(downloadUrl);

            els.progressBar.style.width = '100%';
            els.progressText.textContent = 'Téléchargement terminé !';
            setTimeout(() => els.progressOverlay.classList.add('hidden'), 1800);
        } catch (err) {
            if (err.name === 'AbortError') {
                notify('Téléchargement annulé.', 'success');
            } else {
                notify(err.message || 'Erreur réseau.', 'error');
            }
            els.progressOverlay.classList.add('hidden');
        } finally {
            abortController = null;
        }
    }

    function filenameFrom(disposition) {
        if (!disposition) return null;
        const match = /filename\*?=(?:UTF-8'')?["']?([^;\n"']+)/i.exec(disposition);
        return match ? decodeURIComponent(match[1]).replace(/^["']|["']$/g, '') : null;
    }

    function cancelDownload() {
        if (abortController) abortController.abort();
    }

    // ───────────────────────────── bootstrap ──────────────────────────────

    function init() {
        if (!els.form || !els.urlInput) return;

        applyPlatform(null);
        renderHistory();

        els.form.addEventListener('submit', handleAnalyze);

        els.urlInput.addEventListener('input', () => {
            applyPlatform(detectPlatform(els.urlInput.value.trim()));
        });

        document.querySelectorAll('[data-dl-action]').forEach((btn) => {
            btn.addEventListener('click', () =>
                handleDownload(btn.getAttribute('data-dl-action'))
            );
        });

        if (els.cancelButton) {
            els.cancelButton.addEventListener('click', cancelDownload);
        }
        if (els.historyClear) {
            els.historyClear.addEventListener('click', clearHistory);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
