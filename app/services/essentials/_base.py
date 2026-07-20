"""Metadata + registry pour les outils essentiels.

Chaque outil déclare son `TOOL = Tool(...)` et s'enregistre automatiquement
dans `TOOLS` via `register_tool()`. La homepage et la nav itèrent sur cette
registry plutôt que sur une liste hardcodée.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExternalScript:
    """Script externe avec Subresource Integrity obligatoire.

    Toute ressource servie depuis un CDN doit spécifier un `integrity`
    SHA-384 pour se protéger contre un CDN compromis. `crossorigin` est
    requis par la spec SRI pour les scripts cross-origin.
    """

    src: str
    integrity: str
    crossorigin: str = "anonymous"
    referrerpolicy: str = "no-referrer"

    def as_attrs(self) -> Mapping[str, str]:
        return {
            "src": self.src,
            "integrity": self.integrity,
            "crossorigin": self.crossorigin,
            "referrerpolicy": self.referrerpolicy,
        }


@dataclass(frozen=True)
class Tool:
    """Métadonnées d'un outil essentiel."""

    slug: str
    endpoint: str
    title: str
    short_title: str
    description: str
    caption: str
    icon: str
    accent: str
    category: str = "tools"
    in_nav: bool = True
    external_scripts: tuple[ExternalScript, ...] = field(default_factory=tuple)


TOOLS: list[Tool] = []


def register_tool(tool: Tool) -> Tool:
    """Ajoute un outil à la registry globale (idempotent sur le slug)."""
    if any(existing.slug == tool.slug for existing in TOOLS):
        return tool
    TOOLS.append(tool)
    return tool


def nav_tools(limit: int | None = None) -> list[Tool]:
    """Sous-ensemble pour le menu nav (outils les plus utilisés)."""
    tools = [t for t in TOOLS if t.in_nav]
    if limit is not None:
        tools = tools[:limit]
    return tools
