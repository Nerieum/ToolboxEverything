"""Blueprint parent `essentials` avec auto-enregistrement des sous-outils.

Chaque outil est un module `essentials/<slug>.py` qui expose :
    - `TOOL`: instance `Tool` (metadata)
    - `bp`: `flask.Blueprint` avec `url_prefix="/<slug>"`

L'ajout d'un outil = 1 module Python + 1 template + 1 JS. Aucun enregistrement
manuel ailleurs.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from ._base import TOOLS, Tool, nav_tools, register_tool  # noqa: F401

essentials_bp = Blueprint("essentials", __name__)

# Import des sous-modules : l'ordre définit l'ordre d'affichage sur la
# homepage et dans la nav. Chaque import déclenche register_tool().
from . import (  # noqa: E402,F401
    b64,
    color,
    diff,
    hash_calc,
    json_fmt,
    jwt_decode,
    lorem,
    password,
    qr,
    regex_test,
    timestamp,
    url_encode,
    uuid_gen,
)

for _module in (
    qr,
    password,
    hash_calc,
    b64,
    json_fmt,
    timestamp,
    color,
    uuid_gen,
    jwt_decode,
    regex_test,
    url_encode,
    lorem,
    diff,
):
    essentials_bp.register_blueprint(_module.bp)


@essentials_bp.route("/")
def index():
    """Homepage essentials — liste tous les outils enregistrés."""
    return render_template("essentials/index.html", tools=TOOLS)


__all__ = ["essentials_bp", "TOOLS", "Tool", "register_tool", "nav_tools"]
