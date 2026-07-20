"""Tests d'intégration pour les outils essentials v1.3.2.

Les outils sont désormais 100% client-side — on teste donc que :
  - chaque sous-blueprint est correctement enregistré (GET 200),
  - la homepage liste tous les outils de la registry,
  - le menu nav affiche un sous-ensemble,
  - les anciennes routes API renvoient bien 404 (confirmation de migration).
"""

from __future__ import annotations

import pytest

from app.services.essentials import TOOLS, nav_tools


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.slug)
def test_each_tool_page_renders(client, tool):
    """Chaque outil enregistré répond 200 sur sa page principale
    et charge son script JS via le layout commun.
    """
    with client.application.test_request_context():
        from flask import url_for

        path = url_for(tool.endpoint)
    resp = client.get(path)
    assert resp.status_code == 200, f"{tool.slug} a répondu {resp.status_code}"
    # Le layout commun charge /static/js/essentials/<slug>.js
    assert f"js/essentials/{tool.slug}.js".encode() in resp.data
    # L'icône FA de l'outil apparaît dans l'en-tête du layout
    assert tool.icon.encode() in resp.data


def test_registry_has_all_13_tools():
    """La registry contient bien les 13 outils attendus de la v1.3.2."""
    slugs = {t.slug for t in TOOLS}
    expected = {
        "qr",
        "password",
        "hash",
        "base64",
        "json",
        "timestamp",
        "color",
        "uuid",
        "jwt",
        "regex",
        "url",
        "lorem",
        "diff",
    }
    assert slugs == expected, f"Tools attendus: {expected}, obtenus: {slugs}"


def test_nav_tools_is_subset():
    """nav_tools() retourne un sous-ensemble (pas tous les outils dans la nav)."""
    nav = nav_tools()
    assert 0 < len(nav) < len(TOOLS)
    for t in nav:
        assert t.in_nav is True


def test_nav_tools_limit():
    """Le paramètre limit plafonne le nombre d'outils retournés."""
    assert len(nav_tools(limit=3)) == 3
    assert len(nav_tools(limit=100)) <= len([t for t in TOOLS if t.in_nav])


def test_essentials_index_lists_all_tools(client):
    """La homepage essentials liste chacun des outils (lien présent vers son URL)."""
    resp = client.get("/essentials/")
    assert resp.status_code == 200
    with client.application.test_request_context():
        from flask import url_for

        for tool in TOOLS:
            expected_href = f'href="{url_for(tool.endpoint)}"'.encode()
            assert (
                expected_href in resp.data
            ), f"{tool.slug} absent de la homepage (href {expected_href!r})"


def test_uuid_card_has_indigo_accent(client):
    """La carte UUID garde son fond d'accent sur la homepage essentials."""
    resp = client.get("/essentials/")
    assert resp.status_code == 200
    assert b"site-dropdown__icon site-dropdown__icon--indigo" in resp.data
    assert b"UUID" in resp.data


@pytest.mark.parametrize(
    "path",
    [
        "/essentials/api/qr-code",
        "/essentials/api/password",
        "/essentials/api/hash",
        "/essentials/api/base64",
        "/essentials/api/json/format",
        "/essentials/api/text/process",
        "/essentials/api/url/validate",
        "/essentials/api/colors/palette",
        "/essentials/api/timestamp/convert",
    ],
)
def test_old_api_routes_are_gone(client, path):
    """Les anciennes routes API doivent avoir disparu (tout est client-side)."""
    resp = client.post(path, json={})
    assert resp.status_code == 404
