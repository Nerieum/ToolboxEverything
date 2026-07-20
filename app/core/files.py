"""Utilitaires fichiers partagés.

`sanitize_filename` est la source unique pour produire un nom de fichier sûr et
lisible à partir d'un titre arbitraire (téléchargements, exports). Pour la
validation des uploads entrants, voir `app/core/uploads.py`.
"""

from __future__ import annotations

import re
import unicodedata


def sanitize_filename(filename: str, *, fallback: str = "fichier", max_length: int = 100) -> str:
    """Normalise un nom de fichier : ASCII, sans caractères spéciaux ni espaces.

    Utilisé pour le `download_name` des réponses (téléchargements yt-dlp,
    conversions média) afin d'éviter tout caractère problématique dans les
    en-têtes Content-Disposition.
    """
    if not filename:
        return fallback
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ASCII", "ignore").decode("ASCII")
    filename = re.sub(r"[^\w\s-]", "", filename)
    filename = re.sub(r"[-\s]+", "_", filename)
    return filename.strip("_")[:max_length] or fallback
