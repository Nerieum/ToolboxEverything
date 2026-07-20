"""Générateur de QR codes (100% client-side via qrcode-generator CDN)."""

from __future__ import annotations

from flask import Blueprint, render_template

from ._base import ExternalScript, Tool, register_tool

TOOL = register_tool(
    Tool(
        slug="qr",
        endpoint="essentials.qr.index",
        title="Générateur de QR Code",
        short_title="QR Code",
        description="Créez un QR code à partir de n'importe quel texte ou URL.",
        caption="Créer en un clic",
        icon="fa-qrcode",
        accent="sky",
        category="generate",
        external_scripts=(
            ExternalScript(
                src="https://cdn.jsdelivr.net/npm/qrcode-generator@2.0.4/dist/qrcode.min.js",
                integrity="sha384-o5vdFlIHJf1L/hUFEtj8tgNVtCT+02DKNT3MPA47wJ9Eo5HocC7qCL2YL+sWNsk8",
            ),
        ),
    )
)

bp = Blueprint("qr", __name__, url_prefix="/qr")


@bp.route("/")
def index():
    return render_template("essentials/qr.html", tool=TOOL)
