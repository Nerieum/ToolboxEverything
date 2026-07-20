"""
Toolbox Everything - Application Flask
======================================

Une collection d'outils pratiques pour vos besoins quotidiens :
- Downloader vidéo / audio (YouTube, Vimeo, Dailymotion, TikTok)
- Convertisseur Média
- Outils Essentiels (QR Code, mots de passe, etc.)
- Outils PDF et speedtest
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _read_version() -> str:
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "2.0.0"


__version__ = _read_version()
__author__ = "Doalou"
__license__ = "MIT"


def create_app(*args, **kwargs):
    from .services.main import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["create_app"]
