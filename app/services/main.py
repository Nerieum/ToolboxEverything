"""
Factory Flask de Toolbox Everything.

Tout est initialisé ici pour fonctionner aussi bien sous gunicorn qu'en mode
développement (`python run.py --dev`). La bannière ASCII n'est imprimée qu'une
seule fois (quand `TOOLBOX_PRINT_BANNER=1` — défini par run.py côté dev).
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, Response, g, jsonify, redirect, render_template, request, url_for
from flask_compress import Compress
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from yt_dlp.postprocessor import FFmpegPostProcessor
from yt_dlp.version import __version__ as YT_DLP_VERSION

from app import __version__
from app.core.api import is_json_endpoint
from app.core.rate_limit import limiter
from app.core.security_headers import register_security_headers
from app.core.uploads import configure_pillow_limits
from config import Config

from .downloader.routes import downloader_bp
from .essentials import TOOLS as ESSENTIALS_TOOLS
from .essentials import essentials_bp
from .essentials import nav_tools as essentials_nav_tools
from .media_converter.routes import media_bp
from .pdf_tools.routes import pdf_bp
from .speedtest.routes import speedtest_bp

DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"

TAILWIND_CRITICAL_CLASSES = (
    ".hidden",
    ".flex",
    ".grid",
    ".lg\\:flex",
    ".max-w-7xl",
)

ASSET_REVISION_FILES = (
    "css/tailwind.css",
    "css/style.css",
    "js/main.js",
    "js/shell.js",
    "js/embedded-service.js",
    "img/logo.svg",
)


def _asset_revision(app: Flask) -> str:
    """Empreinte courte des assets critiques, calculée une fois au démarrage."""
    digest = hashlib.sha256()
    static_root = Path(app.static_folder or "")
    for relative_path in ASSET_REVISION_FILES:
        path = static_root / relative_path
        if path.is_file():
            digest.update(path.read_bytes())
    return f"{__version__}-{digest.hexdigest()[:10]}"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _print_banner(app: Flask, ffmpeg_path: str | None) -> None:
    """Bannière ASCII au démarrage (uniquement en dev, jamais sous gunicorn)."""
    use_color = _supports_color()

    def c(code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if use_color else text

    w = 56
    rule = "  " + "-" * w

    def row(label: str, value: str, color: str = CYAN) -> str:
        return f"  |  {label:<18} {c(color, value)}"

    def dot(color: str) -> str:
        return c(color, "*")

    is_dev = app.debug
    mode = "development" if is_dev else "production"
    mode_color = YELLOW if is_dev else GREEN

    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", "8000")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "",
        rule,
        "",
        f"     {c(BOLD, 'Toolbox')} {c(BLUE, 'Everything')}",
        f"     {c(DIM, 'v' + __version__ + '  --  ' + now)}",
        "",
        rule,
        "",
        row("mode", f"{dot(mode_color)} {mode}", mode_color),
        row("url", f"http://{host}:{port}"),
        row(
            "python",
            f"{sys.version_info.major}.{sys.version_info.minor}." f"{sys.version_info.micro}",
        ),
    ]

    if ffmpeg_path:
        lines.append(row("ffmpeg", f"{dot(GREEN)} {os.path.basename(ffmpeg_path)}", GREEN))
    else:
        lines.append(row("ffmpeg", f"{dot(RED)} manquant", RED))

    stirling_url = os.environ.get("STIRLING_PDF_URL", "").strip()
    if stirling_url:
        lines.append(row("stirling-pdf", f"{dot(GREEN)} {stirling_url}", GREEN))
    else:
        lines.append(row("stirling-pdf", f"{dot(YELLOW)} non configure", YELLOW))

    librespeed_url = os.environ.get("LIBRESPEED_URL", "").strip()
    if librespeed_url:
        lines.append(row("librespeed", f"{dot(GREEN)} {librespeed_url}", GREEN))
    else:
        lines.append(row("librespeed", f"{dot(YELLOW)} non configure", YELLOW))

    lines.append(row("uploads", app.config.get("UPLOAD_FOLDER", "-")))
    lines.append("")

    bp_names = sorted(bp.name for bp in app.blueprints.values())
    lines.append(rule)
    lines.append(row("routes", ", ".join(bp_names), DIM))

    if is_dev:
        lines.append("")
        lines.append(
            f"  {c(DIM, '|')}  {c(YELLOW, 'debug')}          "
            f"{c(DIM, 'rechargement auto + logs detailles')}"
        )

    lines.append(rule)
    lines.append("")
    tag = c(GREEN, ">> pret") if not is_dev else c(YELLOW, ">> dev")
    lines.append(f"  {tag}  {c(DIM, f'http://{host}:{port}')}")
    lines.append("")

    print("\n".join(lines), flush=True)


def _configure_logging(app: Flask) -> None:
    """Configure un logging unique (console + fichier avec rotation)."""
    log_file = os.path.abspath(app.config["LOG_FILE"])
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Évite les doublons si create_app est appelé deux fois (tests)
    if any(
        isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == log_file
        for h in app.logger.handlers
    ):
        return

    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(logging.INFO if not app.debug else logging.DEBUG)
        app.logger.addHandler(file_handler)
    except PermissionError:
        # Read-only FS : on se contente du stream handler
        pass

    # En dev ou si Gunicorn est absent, on envoie aussi sur stdout
    if app.debug or not app.logger.handlers:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(fmt)
        stream.setLevel(logging.DEBUG if app.debug else logging.INFO)
        app.logger.addHandler(stream)

    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)


def _tailwind_css_status(app: Flask) -> tuple[bool, list[str]]:
    css_path = Path(app.static_folder or "") / "css" / "tailwind.css"
    if not css_path.exists():
        return False, ["app/static/css/tailwind.css"]

    css = css_path.read_text(encoding="utf-8", errors="replace")
    missing = [selector for selector in TAILWIND_CRITICAL_CLASSES if selector not in css]
    return not missing, missing


def _enforce_tailwind_css_for_docker(app: Flask) -> None:
    ok, missing = _tailwind_css_status(app)
    if ok:
        return

    message = (
        "Asset Tailwind invalide dans l'image Docker "
        f"(manquant/incomplet: {', '.join(missing)}). "
        "Reconstruis l'image avec `docker compose up -d --build`."
    )

    if os.environ.get("DOCKER_ENV") == "1":
        raise RuntimeError(message)

    app.logger.warning(message)


def create_app(config_class: object | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class or Config)
    Config.init_app(app)

    # FFmpeg : une seule source de vérité (config.py)
    ffmpeg_path = app.config.get("FFMPEG_PATH")
    if ffmpeg_path:
        FFmpegPostProcessor._ffmpeg_location.set(ffmpeg_path)

    # Stirling PDF : URL optionnelle pour l'iframe
    app.config["STIRLING_PDF_URL"] = os.environ.get("STIRLING_PDF_URL", "").strip()
    app.config["STIRLING_PDF_PUBLIC_URL"] = os.environ.get(
        "STIRLING_PDF_PUBLIC_URL", app.config["STIRLING_PDF_URL"]
    ).strip()

    # LibreSpeed : URL optionnelle pour l'iframe
    app.config["LIBRESPEED_URL"] = os.environ.get("LIBRESPEED_URL", "").strip()
    app.config["LIBRESPEED_PUBLIC_URL"] = os.environ.get(
        "LIBRESPEED_PUBLIC_URL", app.config["LIBRESPEED_URL"]
    ).strip()

    # Proxy reverse
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Logging (avant toute chose utilisant app.logger)
    _configure_logging(app)

    # En Docker, le CSS Tailwind doit être généré au build de l'image.
    _enforce_tailwind_css_for_docker(app)

    # Compression (sous gunicorn aussi)
    Compress(app)

    # Rate limiter (Redis en prod via RATELIMIT_STORAGE_URI, memory:// en dev)
    limiter.init_app(app)

    # Pillow : plafond de décompression (anti-bombe d'image)
    configure_pillow_limits(50_000_000)

    # Headers HTTP de sécurité (CSP avec nonce, XFO, HSTS, etc.)
    register_security_headers(app)

    # Cache-Control pour les statiques
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 7  # 7 jours

    # Blueprints
    app.register_blueprint(downloader_bp, url_prefix="/downloader")
    app.register_blueprint(media_bp, url_prefix="/media")
    app.register_blueprint(essentials_bp, url_prefix="/essentials")
    app.register_blueprint(pdf_bp, url_prefix="/pdf")
    app.register_blueprint(speedtest_bp, url_prefix="/speedtest")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/downloader")
    def downloader_redirect():
        return redirect(url_for("downloader.index"))

    @app.route("/essentials")
    def essentials_redirect():
        return redirect(url_for("essentials.index"))

    @app.route("/pdf")
    def pdf_redirect():
        return redirect(url_for("pdf.index"))

    @app.route("/speedtest")
    def speedtest_redirect():
        return redirect(url_for("speedtest.index"))

    # --- Backwards-compat : anciens liens /youtube/* ----------------
    # Conserve la compatibilité des liens externes après le rename
    # /youtube/ → /downloader/ (v1.3.2). On utilise 308 pour préserver
    # la méthode HTTP (POST sur /youtube/download → POST /downloader/download).
    _LEGACY_METHODS = ("GET", "POST", "HEAD", "OPTIONS")

    @app.route("/youtube", methods=_LEGACY_METHODS)
    @app.route("/youtube/", methods=_LEGACY_METHODS)
    def _legacy_youtube_root():
        return redirect(url_for("downloader.index"), code=308)

    @app.route("/youtube/<path:subpath>", methods=_LEGACY_METHODS)
    def _legacy_youtube_subpath(subpath: str):
        target = f"/downloader/{subpath}"
        if request.query_string:
            target = f"{target}?{request.query_string.decode('latin-1')}"
        return redirect(target, code=308)

    @app.route("/health")
    @limiter.exempt
    def health() -> Response:
        """Healthcheck (utilisé par Docker) — exempté du rate limiter."""
        status = {
            "status": "ok",
            "version": __version__,
            "yt_dlp": YT_DLP_VERSION,
            "ffmpeg": bool(app.config.get("FFMPEG_PATH")),
            "stirling_pdf": bool(app.config.get("STIRLING_PDF_URL")),
            "librespeed": bool(app.config.get("LIBRESPEED_URL")),
            "tailwind_css": _tailwind_css_status(app)[0],
        }
        return jsonify(status)

    @app.before_request
    def _request_start():
        g.start_time = time.perf_counter()

    @app.after_request
    def _request_end(response: Response) -> Response:
        if request.path.startswith("/static") or request.path == "/health":
            return response
        elapsed = time.perf_counter() - g.get("start_time", time.perf_counter())
        app.logger.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.path,
            response.status_code,
            elapsed * 1000,
        )
        return response

    def _wants_json(req) -> bool:
        # Une vue marquée @json_endpoint répond en JSON, erreurs comprises.
        view = app.view_functions.get(req.endpoint or "")
        if is_json_endpoint(view):
            return True
        if req.is_json:
            return True
        accept = req.headers.get("Accept", "")
        return "application/json" in accept and "text/html" not in accept

    @app.errorhandler(HTTPException)
    def _handle_http(error: HTTPException):
        if _wants_json(request):
            return (
                jsonify(
                    {
                        "error": error.description or error.name,
                        "error_code": error.name.upper().replace(" ", "_"),
                    }
                ),
                error.code or 500,
            )

        template = f"errors/{error.code}.html"
        try:
            return render_template(template), error.code or 500
        except Exception:
            return render_template("errors/500.html"), 500

    @app.errorhandler(Exception)
    def _handle_uncaught(error: Exception):
        app.logger.exception("Unhandled exception")
        return render_template("errors/500.html"), 500

    asset_version = _asset_revision(app)

    @app.context_processor
    def _inject_globals():
        return {
            "current_year": datetime.now().year,
            "app_version": __version__,
            "asset_version": asset_version,
            "stirling_enabled": bool(app.config.get("STIRLING_PDF_URL")),
            "librespeed_enabled": bool(app.config.get("LIBRESPEED_URL")),
            "essentials_tools_all": ESSENTIALS_TOOLS,
            "essentials_tools_nav": essentials_nav_tools(limit=6),
        }

    # Bannière : uniquement si explicitement demandé (run.py en dev)
    if os.environ.get("TOOLBOX_PRINT_BANNER") == "1":
        _print_banner(app, ffmpeg_path)
        # On évite que les re-créations de l'app (tests, reloader) redessinent tout
        os.environ.pop("TOOLBOX_PRINT_BANNER", None)

    return app
