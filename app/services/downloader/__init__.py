"""Module de téléchargement vidéo/audio (yt-dlp).

Supporte un set restreint de plateformes vidéo publiques mainstream :
YouTube, Vimeo, Dailymotion, TikTok. Toute autre URL est rejetée en
amont par `_is_allowed_url` (cf. `routes.py`).
"""

from .routes import ALLOWED_VIDEO_HOSTS, _is_allowed_url, downloader_bp  # noqa: F401

__all__ = ["downloader_bp", "ALLOWED_VIDEO_HOSTS", "_is_allowed_url"]
