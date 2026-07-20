"""
Blueprint `downloader` : extraction d'infos + téléchargement vidéo / audio.

Anciennement `youtube_downloader`, renommé en v1.3.2 puisque l'application
accepte désormais YouTube, Vimeo, Dailymotion et TikTok (cf. la whitelist
`ALLOWED_VIDEO_HOSTS` ci-dessous).

Chaque téléchargement passe par un dossier temporaire auto-nettoyé
(`mkdtemp` + `after_this_request`) et le timeout FFmpeg est plafonné en
amont par yt-dlp.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse

from flask import (
    Blueprint,
    after_this_request,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from yt_dlp import YoutubeDL

from app.core.api import json_endpoint
from app.core.files import sanitize_filename
from app.core.rate_limit import limiter
from config import Config

downloader_bp = Blueprint("downloader", __name__)


# Plateformes vidéo publiques mainstream explicitement autorisées.
# Tout autre domaine est rejeté en amont (yt-dlp supporte >1800 sites,
# beaucoup sont privés ou douteux — pas la peine d'ouvrir cette surface).
ALLOWED_VIDEO_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "vimeo.com",
        "dailymotion.com",
        "dai.ly",
        "tiktok.com",
    }
)

# Mapping host → identifiant de plateforme (utilisé côté UI pour le branding).
PLATFORM_ALIASES: dict[str, str] = {
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "vimeo.com": "vimeo",
    "dailymotion.com": "dailymotion",
    "dai.ly": "dailymotion",
    "tiktok.com": "tiktok",
}


def _is_allowed_url(url: str) -> bool:
    """Vérifie que l'URL est http/https et sur un host whitelisté."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower().lstrip(".")
    if not host:
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_VIDEO_HOSTS)


QUALITY_FORMAT_MAP: dict[str, str] = {
    "highest": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}


def _get_format_string(quality: str) -> str:
    return QUALITY_FORMAT_MAP.get(quality, "bestvideo+bestaudio/best")


def _common_ydl_opts() -> dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        },
    }


def _classify_yt_error(message: str) -> tuple[int, str]:
    """Transforme une erreur yt-dlp en couple (status, message humain)."""
    msg_lower = message.lower()
    if "video unavailable" in msg_lower or "private video" in msg_lower:
        return 400, "Cette vidéo n'est pas accessible (privée, supprimée ou géo-restreinte)."
    if "sign in to confirm your age" in msg_lower:
        return 400, "Cette vidéo nécessite une vérification d'âge."
    if "music premium" in msg_lower or "premium" in msg_lower:
        return 400, "Cette vidéo est réservée aux abonnés premium de la plateforme."
    if "requested format not available" in msg_lower:
        return 400, "Format demandé non disponible pour cette vidéo."
    if "sign in" in msg_lower:
        return 400, "Vidéo nécessitant une connexion (âge ou premium)."
    return 500, f"Erreur : {message}"


_REJECTION_PAYLOAD = {
    "error": (
        "Seules les URLs YouTube, Vimeo, Dailymotion et TikTok "
        "sont acceptées sur cette instance."
    )
}


@downloader_bp.route("/")
def index():
    return render_template("downloader.html")


@downloader_bp.route("/info", methods=["GET"])
@json_endpoint
@limiter.limit("20 per minute")
def get_video_info():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "Paramètre 'url' manquant"}), 400
    if not _is_allowed_url(url):
        return jsonify(_REJECTION_PAYLOAD), 400

    try:
        with YoutubeDL({**_common_ydl_opts(), "extract_flat": False}) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return (
                    jsonify({"error": "Impossible d'obtenir les informations de la vidéo."}),
                    400,
                )

            description = info.get("description") or ""
            return jsonify(
                {
                    "title": info.get("title", "Titre non disponible"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail"),
                    "channel": (info.get("uploader") or info.get("channel") or "Source inconnue"),
                    "views": info.get("view_count", 0),
                    "description": (description[:200] + "...") if description else "",
                    "id": info.get("id"),
                    "formats_available": len(info.get("formats") or []),
                    "extractor": info.get("extractor_key") or info.get("extractor") or "",
                }
            )

    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Downloader info error: %s", exc)
        status, message = _classify_yt_error(str(exc))
        return jsonify({"error": message}), status


@downloader_bp.route("/download", methods=["POST"])
@json_endpoint
@limiter.limit("3 per minute;30 per hour")
def download_video():
    # Validation de la requête d'abord (400), avant la vérification de la
    # capacité serveur FFmpeg (500) : une requête invalide reste un 400 même
    # si FFmpeg est absent.
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante."}), 400
    if not _is_allowed_url(url):
        return jsonify(_REJECTION_PAYLOAD), 400

    ffmpeg_path = Config.get_ffmpeg_path()
    if not ffmpeg_path:
        return jsonify({"error": "FFmpeg requis et introuvable."}), 500

    format_type = data.get("format", "video")
    quality = data.get("quality", "highest")

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    current_app.logger.info(
        "Downloader: url_hash=%s format=%s quality=%s", url_hash, format_type, quality
    )

    temp_dir = tempfile.mkdtemp(prefix="toolbox_dl_")

    @after_this_request
    def _cleanup(response):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("Cleanup error: %s", exc)
        return response

    try:
        base_opts = {
            **_common_ydl_opts(),
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "ffmpeg_location": ffmpeg_path,
        }

        if format_type == "audio":
            ydl_opts = {
                **base_opts,
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": _get_format_string(quality),
                "merge_output_format": "mp4",
                "concurrent_fragment_downloads": 4,
            }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return jsonify({"error": "Impossible de télécharger la vidéo."}), 400

            filepath = None
            requested = info.get("requested_downloads") or []
            if requested:
                filepath = requested[0].get("filepath")

            if not filepath or not os.path.isfile(filepath):
                files = [
                    os.path.join(temp_dir, f)
                    for f in os.listdir(temp_dir)
                    if os.path.isfile(os.path.join(temp_dir, f))
                ]
                if not files:
                    return jsonify({"error": "Aucun fichier généré."}), 500
                filepath = files[0]

            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            current_app.logger.info(
                "Downloader ok: %s (%.2f MB)", os.path.basename(filepath), size_mb
            )

            safe_title = sanitize_filename(info.get("title", "video"), fallback="video")
            ext = "mp3" if format_type == "audio" else "mp4"
            return send_file(
                filepath,
                as_attachment=True,
                download_name=f"{safe_title}.{ext}",
                mimetype="audio/mpeg" if format_type == "audio" else "video/mp4",
            )

    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("Downloader download error: %s", exc)
        status, message = _classify_yt_error(str(exc))
        return jsonify({"error": message}), status
