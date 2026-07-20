"""Tests sur la configuration (Config) : chemins et défauts."""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from config import Config


def test_base_dir_exists():
    import os

    assert os.path.isdir(Config.BASE_DIR)


def test_allowed_extensions_sets():
    assert "jpg" in Config.ALLOWED_IMAGE_EXTENSIONS
    assert "mp4" in Config.ALLOWED_VIDEO_EXTENSIONS
    assert Config.ALLOWED_MEDIA_EXTENSIONS >= Config.ALLOWED_IMAGE_EXTENSIONS
    assert Config.ALLOWED_MEDIA_EXTENSIONS >= Config.ALLOWED_VIDEO_EXTENSIONS


def test_max_content_length_reasonable():
    assert Config.MAX_CONTENT_LENGTH > 1024 * 1024


def test_upload_limits_single_source():
    """Les limites d'upload dérivent bien de Config (source unique)."""
    from app.core import uploads

    assert uploads.MAX_BATCH_FILES == Config.MAX_BATCH_SIZE
    assert uploads.MAX_UPLOAD_BYTES == Config.MAX_CONTENT_LENGTH
    assert uploads.MAX_BATCH_BYTES == Config.MAX_BATCH_BYTES


def test_init_app_preserves_custom_paths(tmp_path):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(
        SECRET_KEY="custom-secret",
        UPLOAD_FOLDER=str(tmp_path / "uploads-custom"),
        TEMP_FOLDER=str(tmp_path / "temp-custom"),
        LOG_FILE=str(tmp_path / "logs-custom" / "app.log"),
        MAX_CONTENT_LENGTH=123_456,
    )

    Config.init_app(app)

    assert app.config["SECRET_KEY"] == "custom-secret"
    assert app.config["MAX_CONTENT_LENGTH"] == 123_456
    assert (tmp_path / "uploads-custom").is_dir()
    assert (tmp_path / "temp-custom").is_dir()
    assert (tmp_path / "logs-custom").is_dir()


def test_stirling_compose_has_no_persistent_storage():
    compose = (Path(__file__).parents[1] / "compose.yml").read_text(encoding="utf-8")
    stirling = compose.split("\n  stirling-pdf:\n", 1)[1].split("\n  librespeed:\n", 1)[0]

    assert "image: stirlingtools/stirling-pdf:2.14.2" in stirling
    assert "\n    volumes:" not in stirling
    assert "STORAGE_ENABLED=false" in stirling
    assert "STORAGE_SHARING_ENABLED=false" in stirling
    for directory in (
        "/configs",
        "/logs",
        "/customFiles",
        "/home/stirlingpdfuser",
        "/pipeline",
        "/storage",
        "/tmp",
    ):
        assert f"- {directory}:" in stirling
