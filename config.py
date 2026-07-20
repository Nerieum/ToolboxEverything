"""
Configuration globale de Toolbox Everything.

Centralise chemins, limites, et quelques listes blanches. La détection FFmpeg
est ici la seule source de vérité — plus de duplication dans `main.py` ou
dans le blueprint downloader.
"""

from __future__ import annotations

import os
import secrets
import shutil
from typing import Any


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))
    SECRET_KEY: str | None = os.environ.get("SECRET_KEY")

    UPLOAD_FOLDER: str = os.path.join(BASE_DIR, "uploads")
    TEMP_FOLDER: str = os.path.join(UPLOAD_FOLDER, "temp")
    LOG_FILE: str = os.path.join(BASE_DIR, "logs", "toolbox.log")

    # Source unique des limites d'upload (consommées par app/core/uploads.py).
    MAX_CONTENT_LENGTH: int = _env_int("MAX_CONTENT_LENGTH", 512 * 1024 * 1024)
    MAX_BATCH_SIZE: int = 20
    MAX_BATCH_BYTES: int = 200 * 1024 * 1024  # taille cumulée d'un batch

    ALLOWED_IMAGE_EXTENSIONS: frozenset[str] = frozenset({"jpg", "jpeg", "png", "gif", "webp"})
    ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset({"mp4", "avi", "mov", "mkv", "webm"})
    ALLOWED_MEDIA_EXTENSIONS: frozenset[str] = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS

    @classmethod
    def get_ffmpeg_path(cls) -> str | None:
        """Résolution unique de FFmpeg (PATH → chemins connus → None)."""
        env_path = os.environ.get("FFMPEG_PATH")
        if env_path and os.path.isfile(env_path):
            return env_path

        ffmpeg_which = shutil.which("ffmpeg")
        if ffmpeg_which:
            return ffmpeg_which

        candidates = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            os.path.join(cls.BASE_DIR, "bin", "ffmpeg.exe"),
            os.path.join(cls.BASE_DIR, "bin", "ffmpeg"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    @classmethod
    def _ensure_secret_key(cls, app: Any) -> str:
        secret_key = app.config.get("SECRET_KEY")
        if not secret_key:
            secret_key = secrets.token_hex(32)
            app.config["SECRET_KEY"] = secret_key
            print(
                "\033[33m[!] SECRET_KEY non configurée — cle aleatoire generee "
                "pour cette session.\033[0m"
            )
        return secret_key

    @staticmethod
    def _ensure_dirs(app: Any) -> None:
        for directory in (
            app.config["UPLOAD_FOLDER"],
            app.config["TEMP_FOLDER"],
            os.path.dirname(app.config["LOG_FILE"]),
        ):
            if directory:
                os.makedirs(directory, exist_ok=True)

    @classmethod
    def init_app(cls, app: Any) -> None:
        # La factory a déjà chargé la config via `from_object`. Toutes les
        # valeurs sont donc lues depuis l'app afin de respecter une éventuelle
        # config de test ou de déploiement personnalisée.
        cls._ensure_secret_key(app)
        cls._ensure_dirs(app)

        # Exposer FFmpeg pour les blueprints (si détecté).
        ffmpeg_path = app.config.get("FFMPEG_PATH") or cls.get_ffmpeg_path()
        if ffmpeg_path:
            app.config["FFMPEG_PATH"] = ffmpeg_path
        elif not os.environ.get("DOCKER_ENV"):
            print(
                "\033[33m[!] FFmpeg introuvable. Installation : "
                "https://www.ffmpeg.org/download.html\033[0m"
            )
