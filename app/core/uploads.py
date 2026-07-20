"""Validation des uploads média (stdlib only).

Historiquement assurée par `app/core/security.py` (supprimé en v1.3.2
car jamais branché sur les routes). Ré-implémentation minimale, testée,
et effectivement appliquée par `media_converter/routes.py`.

Les checks effectués :

1. Extension whitelistée dans `ALLOWED_MEDIA_EXTENSIONS` (config.py)
2. Magic bytes du fichier cohérents avec l'extension déclarée
3. Taille individuelle < `MAX_UPLOAD_BYTES` (512 MB par défaut)
4. Pour le batch : nombre de fichiers et taille cumulée plafonnés

Volontairement sans dépendance externe : `python-magic` / `filetype`
introduisent libmagic (binaire C) pour un bénéfice marginal sur notre
whitelist très étroite.
"""

from __future__ import annotations

from collections.abc import Iterable

from werkzeug.datastructures import FileStorage

from config import Config

# Limites dérivées de la config (source unique) — plus de valeurs en double.
MAX_BATCH_FILES: int = Config.MAX_BATCH_SIZE
MAX_BATCH_BYTES: int = Config.MAX_BATCH_BYTES  # taille cumulée d'un batch
MAX_UPLOAD_BYTES: int = Config.MAX_CONTENT_LENGTH  # taille max par fichier
MAGIC_SNIFF_BYTES: int = 32

_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
    "mp4": (b"ftyp",),
    "mov": (b"ftyp",),
    "webm": (b"\x1a\x45\xdf\xa3",),
    "mkv": (b"\x1a\x45\xdf\xa3",),
    "avi": (b"RIFF",),
}


class UploadRejected(ValueError):
    """Upload rejeté pour cause de sécurité / validation."""


def _peek(stream, size: int) -> bytes:
    pos = stream.tell()
    try:
        return stream.read(size)
    finally:
        stream.seek(pos)


def _ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _signature_matches(ext: str, head: bytes) -> bool:
    """Vérifie la signature du format en tenant compte des conteneurs."""
    signatures = _SIGNATURES.get(ext)
    if not signatures:
        return False

    if ext in {"mp4", "mov"}:
        return len(head) >= 12 and head[4:8] == b"ftyp"

    if ext in {"webp", "avi"}:
        if len(head) < 12 or head[:4] != b"RIFF":
            return False
        marker = head[8:12]
        if ext == "webp":
            return marker == b"WEBP"
        return marker == b"AVI "

    return any(head.startswith(sig) for sig in signatures)


def validate_upload(
    file: FileStorage,
    allowed_extensions: Iterable[str],
    *,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> str:
    """Valide un upload individuel. Retourne l'extension normalisée.

    Ne consomme pas le stream (seek conservé).
    """
    if file is None or not file.filename:
        raise UploadRejected("Fichier manquant ou nom vide.")

    ext = _ext(file.filename)
    if ext not in set(allowed_extensions):
        raise UploadRejected(f"Extension non autorisée : .{ext or '(aucune)'}")

    head = _peek(file.stream, MAGIC_SNIFF_BYTES)
    if not head:
        raise UploadRejected("Fichier vide ou illisible.")

    if not _signature_matches(ext, head):
        raise UploadRejected(
            f"Le contenu du fichier ne correspond pas à l'extension .{ext} "
            "(magic bytes invalides)."
        )

    try:
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
    except (OSError, AttributeError):
        size = 0

    if size and size > max_bytes:
        raise UploadRejected(
            f"Fichier trop volumineux ({size / 1024 / 1024:.1f} MB, "
            f"max {max_bytes / 1024 / 1024:.0f} MB)."
        )

    return ext


def validate_batch(
    files: list[FileStorage],
    allowed_extensions: Iterable[str],
    *,
    max_files: int = MAX_BATCH_FILES,
    max_total_bytes: int = MAX_BATCH_BYTES,
) -> list[tuple[FileStorage, str]]:
    """Valide un batch. Retourne la liste des (file, ext) valides.

    Lève `UploadRejected` dès qu'une limite globale (nombre, taille
    cumulée) est franchie.
    """
    if not files:
        raise UploadRejected("Aucun fichier reçu.")
    if len(files) > max_files:
        raise UploadRejected(f"Trop de fichiers ({len(files)}, max {max_files} par batch).")

    validated: list[tuple[FileStorage, str]] = []
    cumulative = 0
    allowed_set: set[str] = set(allowed_extensions)

    for f in files:
        if not f or not f.filename:
            continue
        ext = validate_upload(f, allowed_set)

        try:
            f.stream.seek(0, 2)
            cumulative += f.stream.tell()
            f.stream.seek(0)
        except (OSError, AttributeError):
            pass

        if cumulative > max_total_bytes:
            raise UploadRejected(
                f"Taille cumulée du batch trop grande "
                f"({cumulative / 1024 / 1024:.1f} MB, "
                f"max {max_total_bytes / 1024 / 1024:.0f} MB)."
            )
        validated.append((f, ext))

    if not validated:
        raise UploadRejected("Aucun fichier valide dans le batch.")
    return validated


def configure_pillow_limits(max_pixels: int | None = 50_000_000) -> None:
    """Plafonne la taille d'image décompressée par Pillow (anti-zip-bomb).

    Sans limite, une image 50000×50000 peut allouer 10 GB de RAM.
    `max_pixels=None` restaure le défaut Pillow (~89 Mpx).
    """
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = max_pixels
