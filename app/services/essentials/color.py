"""Générateur de palettes de couleurs (client-side, HSV)."""

from __future__ import annotations

from flask import Blueprint, render_template

from ._base import Tool, register_tool

TOOL = register_tool(
    Tool(
        slug="color",
        endpoint="essentials.color.index",
        title="Palette de couleurs",
        short_title="Palette",
        description=(
            "Générez une palette harmonieuse à partir d'une couleur de base "
            "(mono, analogue, complémentaire, triadique)."
        ),
        caption="Choisir les bonnes teintes",
        icon="fa-palette",
        accent="pink",
        category="design",
    )
)

bp = Blueprint("color", __name__, url_prefix="/color")


@bp.route("/")
def index():
    return render_template("essentials/color.html", tool=TOOL)
