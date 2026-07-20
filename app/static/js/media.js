// =====================================================================
// Convertisseur média — logique de la page /media.
// Extrait de l'inline script du template (CSP-friendly, self-hosted).
// Utilise le toast global `showNotification` (cf. main.js).
// =====================================================================

const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const fileList = document.getElementById("fileList");
const conversionPanel = document.getElementById("conversionPanel");
const conversionForm = document.getElementById("conversionForm");

let selectedFiles = [];

function updateFileList() {
    fileList.innerHTML = "";
    selectedFiles.forEach((file, index) => {
        const div = document.createElement("div");
        div.className = "media-file";
        const safeName = file.name
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
        div.innerHTML = `
            <div class="media-file__preview">
                ${
                    file.type.startsWith("image/")
                        ? `<img src="${URL.createObjectURL(file)}" class="media-file__image" alt="">`
                        : `<div class="media-file__empty">
                            <i class="fas fa-video"></i>
                           </div>`
                }
            </div>
            <div class="media-file__name">${safeName}</div>
            <button type="button" data-remove-file="${index}"
                    class="media-file__remove" aria-label="Retirer ${safeName}">
                <i class="fas fa-times"></i>
            </button>
        `;
        fileList.appendChild(div);
    });
    conversionPanel.classList.toggle("hidden", selectedFiles.length === 0);
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function handleFiles(files) {
    selectedFiles = selectedFiles.concat(files);
    updateFileList();
}

fileList.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-file]");
    if (!removeButton) return;
    removeFile(Number(removeButton.dataset.removeFile));
});

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
});

const qualityRange = document.querySelector('input[name="quality"]');
const qualityValue = document.getElementById("qualityValue");
if (qualityRange) {
    qualityRange.addEventListener("input", () => {
        qualityValue.textContent = `${qualityRange.value} %`;
    });
}

conversionForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(conversionForm);
    const loadingOverlay = document.getElementById("loadingOverlay");
    const progressBar = document.getElementById("progressBar");
    const progressText = document.getElementById("progressText");

    try {
        loadingOverlay.classList.remove("hidden");

        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            const progress = (i / selectedFiles.length) * 100;

            progressBar.style.width = `${progress}%`;
            progressText.textContent = `Conversion de ${file.name} (${i + 1}/${selectedFiles.length})`;

            try {
                formData.set("file", file);
                const response = await fetch("/media/convert", {
                    method: "POST",
                    body: formData,
                });

                if (!response.ok) {
                    const payload = await response.json().catch(() => ({}));
                    throw new Error(payload.error || "Conversion impossible");
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `converted_${file.name}`;
                a.click();
                URL.revokeObjectURL(url);

                showNotification(`Conversion réussie pour ${file.name}`);
            } catch (error) {
                console.error(error);
                showNotification(`Erreur : ${error.message} (${file.name})`, "error");
            }
        }

        progressBar.style.width = "100%";
        progressText.textContent = "Conversion terminée !";
        await new Promise((resolve) => setTimeout(resolve, 1000));
    } finally {
        loadingOverlay.classList.add("hidden");
        progressBar.style.width = "0%";
        progressText.textContent = "Préparation";
    }
});
