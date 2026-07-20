"""Marqueur pour les vues qui renvoient du JSON.

Les endpoints d'API doivent répondre en JSON même en cas d'erreur (400, 429,
500...). Plutôt que de maintenir une liste de préfixes d'URL en dur dans la
factory (source de désynchronisation), chaque vue concernée se déclare
elle-même via `@json_endpoint`. Le gestionnaire d'erreurs lit ensuite
l'attribut sur la vue effectivement routée.

Placer le décorateur **juste sous** `@bp.route(...)` (donc au-dessus d'un
éventuel `@limiter.limit(...)`) pour que l'attribut soit porté par la vue
enregistrée, quel que soit le wrapping du rate limiter.
"""

from __future__ import annotations

from collections.abc import Callable

_MARKER = "_toolbox_json_endpoint"


def json_endpoint[F: Callable[..., object]](view: F) -> F:
    """Marque une vue comme renvoyant du JSON (erreurs comprises)."""
    setattr(view, _MARKER, True)
    return view


def is_json_endpoint(view: object) -> bool:
    """Indique si `view` a été marquée par `@json_endpoint`."""
    return bool(getattr(view, _MARKER, False))
