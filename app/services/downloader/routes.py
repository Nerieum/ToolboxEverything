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
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from filelock import FileLock
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
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    deno_path = os.getenv("YTDLP_DENO_PATH", "").strip() or shutil.which("deno")
    if deno_path:
        opts["js_runtimes"] = {"deno": {"path": deno_path}}

    cookie_file = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if cookie_file:
        opts["cookiefile"] = cookie_file

    user_agent = os.getenv("YTDLP_USER_AGENT", "").strip()
    if user_agent:
        opts["http_headers"] = {"User-Agent": user_agent}

    return opts


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prepare_cookie_jar(source_file: str, state_dir: Path) -> str:
    """Initialise le cookie jar persistant et le rafraîchit si la source change."""
    source = Path(source_file)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    cookie_jar = state_dir / "youtube-cookies.txt"
    source_marker = state_dir / "youtube-cookies.source.sha256"
    source_digest = _file_sha256(source)

    try:
        previous_digest = source_marker.read_text(encoding="ascii").strip()
    except OSError:
        previous_digest = ""

    if not cookie_jar.is_file() or previous_digest != source_digest:
        cookie_fd, temporary_name = tempfile.mkstemp(
            prefix=".youtube-cookies-", suffix=".tmp", dir=state_dir
        )
        os.close(cookie_fd)
        temporary_cookie_jar = Path(temporary_name)
        try:
            shutil.copyfile(source, temporary_cookie_jar)
            temporary_cookie_jar.chmod(0o600)
            os.replace(temporary_cookie_jar, cookie_jar)
            source_marker.write_text(source_digest, encoding="ascii")
            source_marker.chmod(0o600)
        finally:
            with suppress(FileNotFoundError):
                temporary_cookie_jar.unlink()

    return str(cookie_jar)


@contextmanager
def _youtube_dl(extra_opts: dict[str, Any] | None = None) -> Iterator[YoutubeDL]:
    """Crée une instance yt-dlp avec un cookie jar persistant et sérialisé."""
    opts = {**_common_ydl_opts(), **(extra_opts or {})}
    source_cookie_file = opts.pop("cookiefile", None)

    if not source_cookie_file:
        with YoutubeDL(opts) as ydl:
            yield ydl
        return

    configured_state_dir = os.getenv("YTDLP_COOKIES_STATE_DIR", "").strip()
    state_dir = (
        Path(configured_state_dir)
        if configured_state_dir
        else Path(tempfile.gettempdir()) / "toolbox-ytdlp"
    )
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    with FileLock(state_dir / "youtube-cookies.lock", timeout=900):
        opts["cookiefile"] = _prepare_cookie_jar(source_cookie_file, state_dir)
        with YoutubeDL(opts) as ydl:
            yield ydl


def _classify_yt_error(message: str) -> tuple[int, str]:
    """Transforme une erreur yt-dlp en couple (status, message humain)."""
    msg_lower = message.lower()
    if "not a bot" in msg_lower:
        return (
            503,
            "YouTube bloque les requêtes anonymes de cette instance. "
            "Une session serveur valide est nécessaire.",
        )
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
        with _youtube_dl({"extract_flat": False}) as ydl:
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

        with _youtube_dl(ydl_opts) as ydl:
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
