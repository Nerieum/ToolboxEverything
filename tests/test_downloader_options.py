"""Options partagées du téléchargeur yt-dlp."""

from __future__ import annotations

from pathlib import Path

from app.services.downloader import routes


def test_common_opts_enable_deno_when_available(monkeypatch):
    monkeypatch.delenv("YTDLP_DENO_PATH", raising=False)
    monkeypatch.setattr(routes.shutil, "which", lambda command: "/usr/local/bin/deno")

    opts = routes._common_ydl_opts()

    assert opts["js_runtimes"] == {"deno": {"path": "/usr/local/bin/deno"}}


def test_common_opts_include_optional_authentication(monkeypatch):
    monkeypatch.setenv("YTDLP_COOKIES_FILE", "/run/secrets/youtube-cookies.txt")
    monkeypatch.setenv("YTDLP_USER_AGENT", "Test Browser/1.0")
    monkeypatch.setenv("YTDLP_DENO_PATH", "/opt/deno")

    opts = routes._common_ydl_opts()

    assert opts["cookiefile"] == "/run/secrets/youtube-cookies.txt"
    assert opts["http_headers"] == {"User-Agent": "Test Browser/1.0"}
    assert opts["js_runtimes"] == {"deno": {"path": "/opt/deno"}}


def test_common_opts_leave_authentication_disabled_by_default(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    monkeypatch.delenv("YTDLP_USER_AGENT", raising=False)
    monkeypatch.delenv("YTDLP_DENO_PATH", raising=False)
    monkeypatch.setattr(routes.shutil, "which", lambda command: None)

    opts = routes._common_ydl_opts()

    assert "cookiefile" not in opts
    assert "http_headers" not in opts
    assert "js_runtimes" not in opts


def test_youtube_dl_persists_cookie_updates_without_modifying_source(monkeypatch, tmp_path):
    source = tmp_path / "youtube-cookies.txt"
    source.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    observed: list[tuple[Path, str]] = []

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.cookiefile = Path(opts["cookiefile"])
            observed.append((self.cookiefile, self.cookiefile.read_text(encoding="utf-8")))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.cookiefile.write_text("updated", encoding="utf-8")

    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(source))
    monkeypatch.setenv("YTDLP_COOKIES_STATE_DIR", str(state_dir))
    monkeypatch.setattr(routes, "YoutubeDL", FakeYoutubeDL)

    with routes._youtube_dl() as ydl:
        assert isinstance(ydl, FakeYoutubeDL)
    with routes._youtube_dl():
        pass

    assert source.read_text(encoding="utf-8").startswith("# Netscape")
    assert observed[0][0] == state_dir / "youtube-cookies.txt"
    assert observed[0][1].startswith("# Netscape")
    assert observed[1][1] == "updated"
    assert (state_dir / "youtube-cookies.txt").read_text(encoding="utf-8") == "updated"


def test_youtube_dl_refreshes_cookie_jar_when_source_changes(monkeypatch, tmp_path):
    source = tmp_path / "youtube-cookies.txt"
    source.write_text("first export", encoding="utf-8")
    state_dir = tmp_path / "state"
    observed: list[str] = []

    class FakeYoutubeDL:
        def __init__(self, opts):
            self.cookiefile = Path(opts["cookiefile"])
            observed.append(self.cookiefile.read_text(encoding="utf-8"))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.cookiefile.write_text("server update", encoding="utf-8")

    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(source))
    monkeypatch.setenv("YTDLP_COOKIES_STATE_DIR", str(state_dir))
    monkeypatch.setattr(routes, "YoutubeDL", FakeYoutubeDL)

    with routes._youtube_dl():
        pass
    source.write_text("second export", encoding="utf-8")
    with routes._youtube_dl():
        pass

    assert observed == ["first export", "second export"]


def test_bot_challenge_is_reported_as_temporary_unavailability():
    status, message = routes._classify_yt_error(
        "Sign in to confirm you're not a bot. Use --cookies for authentication"
    )

    assert status == 503
    assert "session serveur" in message.lower()
