"""Tests des couches de sécurité (headers, rate limit, uploads, whitelist yt-dlp).

Ces tests couvrent la surface ajoutée en v1.3.2. Ils ne dépendent pas de
Redis : le limiter tombe sur `memory://` en test (cf. conftest).
"""

from __future__ import annotations

import io

import pytest

from app.core.rate_limit import limiter
from app.core.uploads import (
    MAX_BATCH_FILES,
    UploadRejected,
    validate_batch,
    validate_upload,
)
from app.services.downloader.routes import _is_allowed_url


class _FakeFile:
    """Fake `FileStorage` minimal pour tester `validate_upload`."""

    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.stream = io.BytesIO(content)


@pytest.fixture(autouse=True)
def _reset_limiter(app):
    """Évite que le bucket de rate limit déborde entre les tests."""
    with app.app_context():
        limiter.reset()
    yield
    with app.app_context():
        limiter.reset()


# ─────────────────────────────────────────────────────────────
# Security headers
# ─────────────────────────────────────────────────────────────


class TestSecurityHeaders:
    def test_headers_present_on_html_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        for header in (
            "Content-Security-Policy",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Referrer-Policy",
            "Permissions-Policy",
        ):
            assert header in resp.headers, f"{header} manquant"

    def test_xfo_is_deny(self, client):
        resp = client.get("/")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_nosniff(self, client):
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_csp_includes_nonce_and_self(self, client):
        resp = client.get("/")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "'nonce-" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    def test_csp_nonce_changes_per_request(self, client):
        csp1 = client.get("/").headers["Content-Security-Policy"]
        csp2 = client.get("/").headers["Content-Security-Policy"]
        nonce1 = csp1.split("'nonce-", 1)[1].split("'", 1)[0]
        nonce2 = csp2.split("'nonce-", 1)[1].split("'", 1)[0]
        assert nonce1 and nonce2 and nonce1 != nonce2

    def test_hsts_only_on_https(self, client):
        # HTTP : pas de HSTS.
        assert "Strict-Transport-Security" not in client.get("/").headers
        # HTTPS (simulé via base_url) : HSTS présent.
        secure = client.get("/", base_url="https://localhost")
        assert "Strict-Transport-Security" in secure.headers


# ─────────────────────────────────────────────────────────────
# Validation des uploads (magic bytes)
# ─────────────────────────────────────────────────────────────


IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}


class TestUploadValidation:
    def test_accept_real_png(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        validate_upload(_FakeFile("photo.png", png), IMAGE_EXTS)

    def test_accept_real_jpeg(self):
        jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 28
        validate_upload(_FakeFile("photo.jpg", jpg), IMAGE_EXTS)

    def test_reject_extension_not_in_whitelist(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        with pytest.raises(UploadRejected, match="Extension non autorisée"):
            validate_upload(_FakeFile("exploit.exe", png), IMAGE_EXTS)

    def test_reject_mismatched_magic_bytes(self):
        """PNG déguisé en JPG → rejeté."""
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        with pytest.raises(UploadRejected, match="magic bytes"):
            validate_upload(_FakeFile("fake.jpg", png), IMAGE_EXTS)

    def test_reject_empty_file(self):
        with pytest.raises(UploadRejected, match="vide"):
            validate_upload(_FakeFile("photo.png", b""), IMAGE_EXTS)

    def test_reject_missing_filename(self):
        with pytest.raises(UploadRejected, match="manquant"):
            validate_upload(_FakeFile("", b"\x89PNG\r\n\x1a\n"), IMAGE_EXTS)


class TestBatchValidation:
    @staticmethod
    def _make_pngs(n: int) -> list[_FakeFile]:
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
        return [_FakeFile(f"img{i}.png", png) for i in range(n)]

    def test_accept_small_batch(self):
        validated = validate_batch(self._make_pngs(3), IMAGE_EXTS)
        assert len(validated) == 3

    def test_reject_too_many_files(self):
        with pytest.raises(UploadRejected, match="Trop de fichiers"):
            validate_batch(self._make_pngs(MAX_BATCH_FILES + 1), IMAGE_EXTS)

    def test_reject_empty_batch(self):
        with pytest.raises(UploadRejected, match="Aucun fichier"):
            validate_batch([], IMAGE_EXTS)


# ─────────────────────────────────────────────────────────────
# Whitelist yt-dlp (URL)
# ─────────────────────────────────────────────────────────────


class TestYtdlpUrlWhitelist:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=x",
            "https://music.youtube.com/playlist?list=x",
            "https://vimeo.com/123456",
            "https://player.vimeo.com/video/123",
            "https://www.dailymotion.com/video/x",
            "https://dai.ly/x",
            "https://www.tiktok.com/@user/video/123",
            "https://vm.tiktok.com/ABC123",
        ],
    )
    def test_allowed(self, url: str):
        assert _is_allowed_url(url), f"{url} devrait être autorisé"

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.com/steal",
            "http://malware.ru/bitcoin-miner",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "ftp://internal.corp/leak",
            "",
            "not a url",
            "https://youtube.com.attacker.example.com/",
        ],
    )
    def test_rejected(self, url: str):
        assert not _is_allowed_url(url), f"{url} ne devrait pas être autorisé"

    def test_api_returns_400_on_disallowed_host(self, client):
        resp = client.get("/downloader/info?url=https://evil.example.com/vid")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data and "YouTube" in data["error"]

    def test_download_returns_400_on_disallowed_host(self, client):
        resp = client.post(
            "/downloader/download",
            json={"url": "https://evil.example.com/vid", "format": "video"},
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# Rate limiter
# ─────────────────────────────────────────────────────────────


class TestRateLimit:
    def test_health_exempted(self, client):
        """/health doit toujours répondre, même en flood."""
        codes = [client.get("/health").status_code for _ in range(30)]
        assert all(c == 200 for c in codes)

    def test_downloader_info_limited_at_20_per_minute(self, client):
        """La 21e requête à /downloader/info doit être 429."""
        bad_url = "https://evil.example.com/vid"  # rejetée avant yt-dlp
        statuses: list[int] = []
        for _ in range(22):
            statuses.append(client.get(f"/downloader/info?url={bad_url}").status_code)

        assert (
            statuses[:20].count(400) == 20
        ), f"Les 20 premières devraient être 400 (URL rejected), got {statuses[:20]}"
        assert 429 in statuses[20:], f"Le rate limit aurait dû déclencher 429, got {statuses[20:]}"

    def test_ratelimit_response_is_json_for_api_routes(self, client):
        bad_url = "https://evil.example.com/vid"
        for _ in range(20):
            client.get(f"/downloader/info?url={bad_url}")
        resp = client.get(f"/downloader/info?url={bad_url}")
        assert resp.status_code == 429
        assert resp.is_json, "Les erreurs sur routes API doivent être en JSON"
