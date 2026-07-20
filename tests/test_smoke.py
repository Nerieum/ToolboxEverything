"""Tests smoke : routes principales, health, PDF fallback."""

from __future__ import annotations

from pathlib import Path


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "yt_dlp" in data
    assert data["tailwind_css"] is True


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Toolbox" in resp.data
    assert b"v2.0.0" in resp.data
    assert b"Speedtest" in resp.data
    assert b"/speedtest/" in resp.data


def test_version_file_is_release_source():
    assert Path("VERSION").read_text(encoding="utf-8").strip() == "2.0.0"


def test_base_template_loads_local_css_assets(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"css/tailwind.css" in resp.data
    assert b"css/style.css" in resp.data


def test_header_controls_are_csp_safe(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'id="themeToggle"' in resp.data
    assert b'aria-pressed="false"' in resp.data
    assert b"theme-toggle__icon--sun" in resp.data
    assert b"theme-toggle__icon--moon" in resp.data
    assert b"header-icon-button--mobile" in resp.data
    assert b'id="mobileMenu" class="mobile-menu hidden"' in resp.data
    assert b"onclick=" not in resp.data


def test_main_pages_do_not_use_inline_click_handlers(client):
    for path in ("/", "/media/", "/essentials/", "/pdf/", "/speedtest/"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert b"onclick=" not in resp.data, f"{path} contient encore un onclick inline"


def test_main_pages_have_clean_visible_copy(client):
    forbidden = [
        "—",
        "–",
        "…",
        "quelques clics",
        "tout-en-un",
        "utile et propre",
        "embarque",
    ]
    for path in ("/", "/downloader/", "/media/", "/essentials/", "/pdf/", "/speedtest/"):
        resp = client.get(path)
        assert resp.status_code == 200
        html = resp.data.decode("utf-8", errors="replace")
        found = [token for token in forbidden if token in html]
        assert not found, f"{path} contient encore {found}"


def test_responsive_header_css_is_not_overridden():
    from pathlib import Path

    css = Path("app/static/css/style.css").read_text(encoding="utf-8")
    assert ".site-header__nav-center {\n    display: none;" in css
    assert "@media (min-width: 1180px)" in css
    assert ".header-icon-button--mobile" in css
    assert ".theme-toggle__icon--sun" in css
    assert ".theme-toggle__icon--moon" in css
    assert ".media-file-grid" in css
    assert ".home-cover" in css
    assert ".home-workbench" in css
    assert ".home-tool" in css
    assert "[hidden] {\n    display: none !important;" in css
    assert ".mobile-menu__submenu.hidden" in css
    assert ".tool-overlay.hidden" in css


def test_downloader_index(client):
    resp = client.get("/downloader/")
    assert resp.status_code == 200


def test_legacy_youtube_redirects_to_downloader(client):
    """Compat ascendante après le rename /youtube → /downloader (v1.3.2)."""
    resp = client.get("/youtube/", follow_redirects=False)
    assert resp.status_code in (301, 308)
    assert "/downloader" in resp.headers["Location"]


def test_media_index(client):
    resp = client.get("/media/")
    assert resp.status_code == 200


def test_essentials_index(client):
    resp = client.get("/essentials/")
    assert resp.status_code == 200


def test_pdf_fallback_when_not_configured(client, app):
    """Sans STIRLING_PDF_URL, la page explique comment configurer."""
    prev_i = app.config.get("STIRLING_PDF_URL")
    prev_p = app.config.get("STIRLING_PDF_PUBLIC_URL")
    app.config["STIRLING_PDF_URL"] = ""
    app.config["STIRLING_PDF_PUBLIC_URL"] = ""
    try:
        resp = client.get("/pdf/")
        assert resp.status_code == 200
        assert b"Stirling" in resp.data
        assert b"docker compose up -d stirling-pdf" in resp.data
        assert b"service-offline" in resp.data
    finally:
        app.config["STIRLING_PDF_URL"] = prev_i or ""
        app.config["STIRLING_PDF_PUBLIC_URL"] = prev_p or ""


def test_pdf_status_not_configured(client, app):
    prev = app.config.get("STIRLING_PDF_URL")
    app.config["STIRLING_PDF_URL"] = ""
    try:
        resp = client.get("/pdf/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is False
    finally:
        app.config["STIRLING_PDF_URL"] = prev or ""


def test_speedtest_fallback_when_not_configured(client, app):
    """Sans LIBRESPEED_URL, la page explique comment configurer."""
    prev_i = app.config.get("LIBRESPEED_URL")
    prev_p = app.config.get("LIBRESPEED_PUBLIC_URL")
    app.config["LIBRESPEED_URL"] = ""
    app.config["LIBRESPEED_PUBLIC_URL"] = ""
    try:
        resp = client.get("/speedtest/")
        assert resp.status_code == 200
        assert b"LibreSpeed" in resp.data
        assert b"docker compose up -d librespeed" in resp.data
        assert b"service-offline" in resp.data
    finally:
        app.config["LIBRESPEED_URL"] = prev_i or ""
        app.config["LIBRESPEED_PUBLIC_URL"] = prev_p or ""


def test_speedtest_status_not_configured(client, app):
    prev = app.config.get("LIBRESPEED_URL")
    app.config["LIBRESPEED_URL"] = ""
    try:
        resp = client.get("/speedtest/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is False
    finally:
        app.config["LIBRESPEED_URL"] = prev or ""


def test_speedtest_redirect(client):
    resp = client.get("/speedtest", follow_redirects=False)
    assert resp.status_code in (301, 302, 308)


def test_404_returns_html(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404


def test_essentials_redirect(client):
    resp = client.get("/essentials", follow_redirects=False)
    assert resp.status_code in (301, 302, 308)


def test_downloader_info_requires_url(client):
    resp = client.get("/downloader/info")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_downloader_download_requires_body(client):
    resp = client.post("/downloader/download", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_pdf_configured_renders_iframe(client, app):
    prev_i = app.config.get("STIRLING_PDF_URL")
    prev_p = app.config.get("STIRLING_PDF_PUBLIC_URL")
    app.config["STIRLING_PDF_URL"] = "http://stirling-pdf:8080"
    app.config["STIRLING_PDF_PUBLIC_URL"] = "http://localhost:8080"
    try:
        resp = client.get("/pdf/")
        assert resp.status_code == 200
        assert b"http://localhost:8080" in resp.data
        assert b"pdf-frame" in resp.data
        assert b'data-service-status="/pdf/status"' in resp.data
        assert b"js/embedded-service.js" in resp.data
    finally:
        app.config["STIRLING_PDF_URL"] = prev_i or ""
        app.config["STIRLING_PDF_PUBLIC_URL"] = prev_p or ""


def test_pdf_status_configured_reachable(client, app, monkeypatch):
    import app.services.pdf_tools.routes as pdf_routes

    app.config["STIRLING_PDF_URL"] = "http://stirling-pdf:8080"
    monkeypatch.setattr(
        pdf_routes,
        "probe",
        lambda url, **kw: {"enabled": True, "reachable": True, "status_code": 200},
    )
    try:
        resp = client.get("/pdf/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["enabled"] is True
        assert data["reachable"] is True
    finally:
        app.config["STIRLING_PDF_URL"] = ""


def test_speedtest_configured_renders_iframe(client, app):
    prev_i = app.config.get("LIBRESPEED_URL")
    prev_p = app.config.get("LIBRESPEED_PUBLIC_URL")
    app.config["LIBRESPEED_URL"] = "http://librespeed"
    app.config["LIBRESPEED_PUBLIC_URL"] = "http://localhost:8081"
    try:
        resp = client.get("/speedtest/")
        assert resp.status_code == 200
        assert b"http://localhost:8081" in resp.data
        assert b'data-service-status="/speedtest/status"' in resp.data
        assert b"js/embedded-service.js" in resp.data
    finally:
        app.config["LIBRESPEED_URL"] = prev_i or ""
        app.config["LIBRESPEED_PUBLIC_URL"] = prev_p or ""


def test_editorial_design_system_present(client):
    """La refonte 2.0.0 : tokens, Fraunces et accueil éditorial."""
    css = Path("app/static/css/style.css").read_text(encoding="utf-8")
    assert ":root {" in css
    assert "--accent:" in css
    assert "--paper:" in css
    assert ".dark {" in css
    assert "@font-face" in css
    assert ".home-cover" in css
    assert ".home-workbench" in css

    resp = client.get("/")
    assert resp.status_code == 200
    assert b"fraunces-var.woff2" in resp.data
    assert b"home-tool__title" in resp.data
    assert "Les outils qu’on finit".encode() in resp.data
    assert b"Pas de compte" in resp.data
    assert b"Pourquoi utiliser nos outils" not in resp.data
    assert b"js/shell.js" in resp.data
    assert b"css/style.css?v=2.0.0-" in resp.data
