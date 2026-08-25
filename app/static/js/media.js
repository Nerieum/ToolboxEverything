// =====================================================================
// Convertisseur média — logique de la page /media.
//
// Monobloc de dépôt + un bloc par fichier. Les réglages sont groupés
// par famille (images, vidéos, audio) ; « Tout convertir » traite la
// file séquentiellement (un fichier à la fois, progression d'envoi
// par bloc). L'archive .zip est assemblée côté client par JSZip.
// Utilise le toast global `showNotification` (cf. main.js).
// =====================================================================

const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const settingsPanel = document.getElementById("convSettings");
const grid = document.getElementById("convGrid");
const convertAllBtn = document.getElementById("convertAll");
const zipRow = document.getElementById("zipRow");
const downloadZipBtn = document.getElementById("downloadZip");
const qualityRange = document.getElementById("media-quality");
const qualityValue = document.getElementById("qualityValue");
const bitrateSelect = document.getElementById("audioBitrate");

const IMAGE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "mkv", "mov", "avi"]);
const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "flac", "ogg", "m4a"]);
const AUDIO_FORMATS = new Set(["mp3", "wav", "flac", "ogg", "m4a"]);

const FAMILY_INITIALS = { image: "I", video: "V", audio: "A" };

let nextId = 1;
const items = new Map();
let converting = false;

function fileFamily(name) {
    const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
    if (VIDEO_EXTENSIONS.has(ext)) return "video";
    if (AUDIO_EXTENSIONS.has(ext)) return "audio";
    if (IMAGE_EXTENSIONS.has(ext)) return "image";
    return null;
}

function formatSize(bytes) {
    if (bytes >= 1024 * 1024) {
        return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} Mo`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} Ko`;
}

function targetFormatFor(family) {
    return document.querySelector(`[data-format-select="${family}"]`).value;
}

// Nom renvoyé par le serveur (Content-Disposition), sinon reconstruit.
function filenameFromResponse(xhr, fallback) {
    const header = xhr.getResponseHeader("Content-Disposition") || "";
    const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8) return decodeURIComponent(utf8[1]);
    const plain = header.match(/filename="?([^";]+)"?/i);
    if (plain) return plain[1];
    return fallback;
}

// ------------------------------------------------------------------
// Rendu des blocs
// ------------------------------------------------------------------

function renderStatus(item) {
    const status = item.node.querySelector("[data-status]");
    const action = item.node.querySelector("[data-action]");
    status.textContent = "";
    action.textContent = "";

    if (item.state === "waiting") {
        status.textContent = "En attente";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "conv-block__link";
        remove.textContent = "Retirer";
        remove.addEventListener("click", () => {
            items.delete(item.id);
            item.node.remove();
            refreshChrome();
        });
        action.appendChild(remove);
    } else if (item.state === "uploading" || item.state === "converting") {
        const track = document.createElement("span");
        track.className = "conv-progress";
        const bar = document.createElement("span");
        bar.className = "conv-progress__bar";
        if (item.state === "converting") {
            bar.classList.add("conv-progress__bar--indeterminate");
        } else {
            bar.style.width = `${item.progress}%`;
        }
        track.appendChild(bar);
        status.appendChild(track);
        const label = document.createElement("span");
        label.className = "conv-block__state";
        label.textContent =
            item.state === "uploading" ? `envoi ${item.progress} %` : "conversion";
        status.appendChild(label);

        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "conv-block__link";
        cancel.textContent = "Annuler";
        cancel.addEventListener("click", () => {
            if (item.xhr) item.xhr.abort();
        });
        action.appendChild(cancel);
    } else if (item.state === "done") {
        const ok = document.createElement("span");
        ok.className = "conv-block__ok";
        const saved = item.file.size - item.result.size;
        const delta = saved > 0 ? ` · −${Math.round((saved / item.file.size) * 100)} %` : "";
        ok.textContent = `${formatSize(item.result.size)}${delta}`;
        status.appendChild(ok);

        const download = document.createElement("a");
        download.className = "conv-block__download";
        download.textContent = "Télécharger";
        download.href = item.resultUrl;
        download.download = item.resultName;
        action.appendChild(download);
    } else if (item.state === "error") {
        const err = document.createElement("span");
        err.className = "conv-block__error";
        err.textContent = item.error;
        status.appendChild(err);

        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "conv-block__link";
        retry.textContent = "Réessayer";
        retry.addEventListener("click", () => {
            item.state = "waiting";
            renderStatus(item);
            renderMeta(item);
            refreshChrome();
        });
        action.appendChild(retry);
    }
}

function renderMeta(item) {
    const meta = item.node.querySelector("[data-meta]");
    const target = targetFormatFor(item.family).toUpperCase();
    meta.textContent = `${formatSize(item.file.size)} · vers ${target}`;
}

function createBlock(file) {
    const family = fileFamily(file.name);
    if (!family) {
        showNotification(`Format non pris en charge : ${file.name}`, "error");
        return;
    }

    const item = {
        id: nextId++,
        file,
        family,
        state: "waiting",
        progress: 0,
        xhr: null,
        result: null,
        resultUrl: null,
        resultName: null,
        error: null,
        node: null,
    };

    const block = document.createElement("div");
    block.className = `conv-block conv-block--${family}`;

    const ghost = document.createElement("span");
    ghost.className = "conv-block__ghost";
    ghost.setAttribute("aria-hidden", "true");
    ghost.textContent = FAMILY_INITIALS[family];

    const name = document.createElement("strong");
    name.className = "conv-block__name";
    name.textContent = file.name;
    name.title = file.name;

    const meta = document.createElement("span");
    meta.className = "conv-block__meta";
    meta.dataset.meta = "";

    const footer = document.createElement("span");
    footer.className = "conv-block__footer";
    const status = document.createElement("span");
    status.className = "conv-block__status";
    status.dataset.status = "";
    const action = document.createElement("span");
    action.dataset.action = "";
    footer.append(status, action);

    block.append(ghost, name, meta, footer);
    grid.appendChild(block);

    item.node = block;
    items.set(item.id, item);
    renderMeta(item);
    renderStatus(item);
}

function refreshChrome() {
    const families = new Set([...items.values()].map((item) => item.family));
    const hasItems = items.size > 0;

    grid.hidden = !hasItems;
    settingsPanel.hidden = !hasItems;

    document.querySelectorAll("[data-family-block]").forEach((label) => {
        label.hidden = !families.has(label.dataset.familyBlock);
    });

    // Qualité : images et vidéos. Débit : audio, ou vidéos ciblant l'audio.
    const videoTargetsAudio =
        families.has("video") && AUDIO_FORMATS.has(targetFormatFor("video"));
    const qualityBlock = document.querySelector("[data-quality-block]");
    const bitrateBlock = document.querySelector("[data-bitrate-block]");
    qualityBlock.hidden = !(
        families.has("image") ||
        (families.has("video") && !videoTargetsAudio)
    );
    bitrateBlock.hidden = !(families.has("audio") || videoTargetsAudio);

    const doneCount = [...items.values()].filter((item) => item.state === "done").length;
    zipRow.hidden = !(doneCount > 0 && typeof JSZip !== "undefined");

    convertAllBtn.disabled = converting;
    convertAllBtn.textContent = converting ? "Conversion en cours" : "Tout convertir";
}

// ------------------------------------------------------------------
// Conversion (séquentielle, un fichier à la fois)
// ------------------------------------------------------------------

function convertItem(item) {
    return new Promise((resolve) => {
        const formData = new FormData();
        formData.set("file", item.file);
        formData.set("format", targetFormatFor(item.family));
        formData.set("quality", qualityRange.value);
        formData.set("bitrate", bitrateSelect.value);

        const xhr = new XMLHttpRequest();
        item.xhr = xhr;
        xhr.open("POST", "/media/convert");
        xhr.responseType = "blob";

        xhr.upload.addEventListener("progress", (event) => {
            if (!event.lengthComputable) return;
            item.progress = Math.round((event.loaded / event.total) * 100);
            if (item.progress >= 100) item.state = "converting";
            renderStatus(item);
        });

        xhr.addEventListener("load", async () => {
            item.xhr = null;
            if (xhr.status === 200) {
                item.result = xhr.response;
                if (item.resultUrl) URL.revokeObjectURL(item.resultUrl);
                item.resultUrl = URL.createObjectURL(item.result);
                item.resultName = filenameFromResponse(
                    xhr,
                    `converted_${item.file.name}`,
                );
                item.state = "done";
            } else {
                let message = "Conversion impossible";
                try {
                    message = JSON.parse(await xhr.response.text()).error || message;
                } catch {
                    /* réponse non JSON : message générique */
                }
                item.state = "error";
                item.error = message;
            }
            renderStatus(item);
            refreshChrome();
            resolve();
        });

        const fail = (label) => () => {
            item.xhr = null;
            item.state = "error";
            item.error = label;
            renderStatus(item);
            refreshChrome();
            resolve();
        };
        xhr.addEventListener("error", fail("Erreur réseau"));
        xhr.addEventListener("abort", fail("Annulé"));

        item.state = "uploading";
        item.progress = 0;
        renderStatus(item);
        xhr.send(formData);
    });
}

convertAllBtn.addEventListener("click", async () => {
    if (converting) return;
    const pending = [...items.values()].filter(
        (item) => item.state === "waiting" || item.state === "error",
    );
    if (!pending.length) return;

    converting = true;
    refreshChrome();
    for (const item of pending) {
        // eslint-disable-next-line no-await-in-loop
        await convertItem(item);
    }
    converting = false;
    refreshChrome();

    const failed = pending.filter((item) => item.state === "error").length;
    if (failed === 0) {
        showNotification("Conversion terminée.");
    } else {
        showNotification(`Conversion terminée, ${failed} fichier(s) en échec.`, "error");
    }
});

// ------------------------------------------------------------------
// Archive .zip (JSZip, côté client)
// ------------------------------------------------------------------

downloadZipBtn.addEventListener("click", async () => {
    const done = [...items.values()].filter((item) => item.state === "done");
    if (!done.length || typeof JSZip === "undefined") return;

    const zip = new JSZip();
    const used = new Set();
    done.forEach((item) => {
        let name = item.resultName;
        let suffix = 2;
        while (used.has(name)) {
            const dot = item.resultName.lastIndexOf(".");
            name = `${item.resultName.slice(0, dot)}_${suffix}${item.resultName.slice(dot)}`;
            suffix += 1;
        }
        used.add(name);
        zip.file(name, item.result);
    });

    const blob = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "conversions.zip";
    a.click();
    URL.revokeObjectURL(url);
});

// ------------------------------------------------------------------
// Dépôt de fichiers et réglages
// ------------------------------------------------------------------

function handleFiles(files) {
    files.forEach(createBlock);
    refreshChrome();
}

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("is-dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("is-dragover");
});

dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("is-dragover");
    handleFiles(Array.from(e.dataTransfer.files));
});

fileInput.addEventListener("change", (e) => {
    handleFiles(Array.from(e.target.files));
    fileInput.value = "";
});

qualityRange.addEventListener("input", () => {
    qualityValue.textContent = `${qualityRange.value} %`;
});

document.querySelectorAll("[data-format-select]").forEach((select) => {
    select.addEventListener("change", () => {
        items.forEach((item) => {
            if (item.family === select.dataset.formatSelect) renderMeta(item);
        });
        refreshChrome();
    });
});
