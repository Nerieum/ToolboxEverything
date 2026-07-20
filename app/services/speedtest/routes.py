"""
Blueprint Speedtest.

Toolbox embarque LibreSpeed via une iframe. L'URL peut être :

- `LIBRESPEED_URL` : URL interne utilisée pour le healthcheck
  (ex. `http://librespeed` sous Docker).
- `LIBRESPEED_PUBLIC_URL` : URL exposée au navigateur dans l'iframe
  (ex. `http://localhost:8081` ou un sous-domaine public). Par défaut,
  identique à `LIBRESPEED_URL`.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from app.core.api import json_endpoint
from app.core.rate_limit import limiter
from app.services._embedded import NOT_CONFIGURED, internal_url, probe, public_url

speedtest_bp = Blueprint("speedtest", __name__, template_folder="../../templates")


@speedtest_bp.route("/")
def index():
    public = public_url("LIBRESPEED_PUBLIC_URL", "LIBRESPEED_URL")
    return render_template(
        "speedtest.html",
        librespeed_public_url=public,
        librespeed_configured=bool(public),
    )


@speedtest_bp.route("/status")
@json_endpoint
@limiter.limit("60 per minute")
def status():
    """Ping rapide de l'instance LibreSpeed (utilisé pour l'UI)."""
    internal = internal_url("LIBRESPEED_URL")
    if not internal:
        return jsonify(NOT_CONFIGURED), 200
    return jsonify(probe(internal)), 200
