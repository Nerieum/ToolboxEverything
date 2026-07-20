"""
Blueprint PDF.

Toolbox n'implémente pas ses propres outils PDF ; on embarque Stirling PDF
(https://github.com/Stirling-Tools/Stirling-PDF) via une iframe. L'URL peut
être :

- `STIRLING_PDF_URL` : URL interne utilisée pour le healthcheck (ex.
  `http://stirling-pdf:8080` sous Docker).
- `STIRLING_PDF_PUBLIC_URL` : URL exposée au navigateur dans l'iframe
  (ex. `http://localhost:8080` ou un sous-domaine public). Par défaut,
  identique à `STIRLING_PDF_URL`.

Si aucune URL n'est définie, on affiche un message expliquant comment
l'activer.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template

from app.core.api import json_endpoint
from app.core.rate_limit import limiter
from app.services._embedded import NOT_CONFIGURED, internal_url, probe, public_url

pdf_bp = Blueprint("pdf", __name__, template_folder="../../templates")


@pdf_bp.route("/")
def index():
    public = public_url("STIRLING_PDF_PUBLIC_URL", "STIRLING_PDF_URL")
    return render_template(
        "pdf.html",
        stirling_public_url=public,
        stirling_configured=bool(public),
    )


@pdf_bp.route("/status")
@json_endpoint
@limiter.limit("60 per minute")
def status():
    """Ping rapide de l'instance Stirling PDF (utilisé pour l'UI)."""
    internal = internal_url("STIRLING_PDF_URL")
    if not internal:
        return jsonify(NOT_CONFIGURED), 200

    # 1) Endpoint de statut dédié. On le garde s'il est joignable (<500) ou s'il
    #    a échoué au niveau réseau (on remonte alors l'erreur).
    result = probe(f"{internal}/api/v1/info/status")
    if result.get("reachable") or "reason" in result:
        return jsonify(result), 200

    # 2) Fallback : ping de la racine (Stirling a répondu ≥500 sur l'API).
    return jsonify(probe(internal)), 200
