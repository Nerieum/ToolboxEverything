"""Helpers partagés pour les services embarqués via iframe (Stirling PDF,
LibreSpeed).

Chaque service expose deux URLs de config :

- une URL *interne* (réseau Docker) pour le healthcheck côté serveur ;
- une URL *publique* (navigateur) pour l'iframe, par défaut égale à l'interne.

`pdf_tools` et `speedtest` partageaient un code quasi identique de résolution
d'URL et de ping ; il est centralisé ici. Les réponses JSON restent
inchangées.
"""

from __future__ import annotations

import requests
from flask import current_app

_UA = {"User-Agent": "Toolbox-Everything"}

NOT_CONFIGURED = {"enabled": False, "reachable": False, "reason": "not_configured"}


def public_url(public_key: str, internal_key: str) -> str:
    """URL exposée au navigateur (publique, sinon interne), sans slash final."""
    cfg = current_app.config
    return (cfg.get(public_key) or cfg.get(internal_key) or "").rstrip("/")


def internal_url(internal_key: str) -> str:
    """URL interne pour le healthcheck serveur, sans slash final."""
    return (current_app.config.get(internal_key) or "").rstrip("/")


def probe(url: str, *, timeout: int = 3) -> dict:
    """Ping HTTP simple → payload de statut normalisé (enabled/reachable)."""
    try:
        resp = requests.get(url, timeout=timeout, headers=_UA)
        return {
            "enabled": True,
            "reachable": resp.status_code < 500,
            "status_code": resp.status_code,
        }
    except requests.RequestException as exc:
        return {"enabled": True, "reachable": False, "reason": str(exc)}
