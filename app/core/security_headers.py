"""Headers HTTP de sécurité (CSP stricte, XFO, nosniff, HSTS, etc.).

Principes :

- **CSP avec nonce par requête** : aucun script inline n'est accepté
  sans un nonce cryptographique généré à chaque requête. Les scripts
  externes doivent être sur `'self'` ou dans la whitelist (SRI requis
  côté template).
- **Frame protection** :
    * `frame-ancestors 'none'` → personne ne peut embed Toolbox
    * `X-Frame-Options: DENY` (fallback pour vieux navigateurs)
- **HSTS** activé uniquement sur HTTPS (détecté via `request.is_secure`
  ou `X-Forwarded-Proto` grâce à ProxyFix).
- **Referrer-Policy** : `strict-origin-when-cross-origin` = bon compromis
  analytics/vie privée.
- **Permissions-Policy** : désactive tout ce que l'app n'utilise pas
  (caméra, micro, géoloc, USB, paiement, etc.).

Le nonce est exposé aux templates via `g.csp_nonce` et un context
processor `{{ csp_nonce }}`.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Iterable

from flask import Flask, Response, g, request

# Domaines externes autorisés pour les scripts (CDN).
# Tout nouvel ajout doit s'accompagner d'un `integrity=` SRI côté template.
_ALLOWED_SCRIPT_CDNS = ("https://cdn.jsdelivr.net",)


def _build_csp(nonce: str, frame_src_extra: Iterable[str] = ()) -> str:
    frame_src = " ".join(["'self'", *frame_src_extra]).strip()
    script_src = " ".join(
        [
            "'self'",
            f"'nonce-{nonce}'",
            *_ALLOWED_SCRIPT_CDNS,
        ]
    )
    directives = [
        "default-src 'self'",
        f"script-src {script_src}",
        # 'unsafe-inline' sur style-src : toléré car le code applicatif
        # génère des `style="..."` dynamiques (couleurs d'accent tool).
        # Sans impact sur XSS tant que script-src est strict.
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        # Les miniatures du downloader pointent sur des CDN externes (i.ytimg.com,
        # vumbnail.com, etc.). On autorise tout HTTPS, jamais HTTP — la surface
        # d'attaque est nulle vu que script-src reste strict.
        "img-src 'self' data: blob: https:",
        "media-src 'self' blob:",
        "connect-src 'self'",
        f"frame-src {frame_src}",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
        "worker-src 'self' blob:",
        "upgrade-insecure-requests",
    ]
    return "; ".join(directives)


_PERMISSIONS_POLICY = ", ".join(
    [
        "accelerometer=()",
        "ambient-light-sensor=()",
        "autoplay=(self)",
        "camera=()",
        "display-capture=()",
        "encrypted-media=()",
        "fullscreen=(self)",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "midi=()",
        "payment=()",
        "picture-in-picture=(self)",
        "publickey-credentials-get=()",
        "screen-wake-lock=()",
        "sync-xhr=()",
        "usb=()",
        "web-share=()",
        "xr-spatial-tracking=()",
    ]
)


def register_security_headers(app: Flask) -> None:
    """Branche le nonce + les headers sur l'app Flask."""

    frame_extra = tuple(
        url
        for url in (
            os.environ.get("STIRLING_PDF_PUBLIC_URL", "").strip(),
            os.environ.get("LIBRESPEED_PUBLIC_URL", "").strip(),
        )
        if url
    )

    @app.before_request
    def _csp_nonce() -> None:
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _inject_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def _apply_headers(resp: Response) -> Response:
        nonce = getattr(g, "csp_nonce", "") or secrets.token_urlsafe(16)
        resp.headers.setdefault(
            "Content-Security-Policy",
            _build_csp(nonce, frame_extra),
        )
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        if request.is_secure:
            resp.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return resp
