"""Tests du sanitizer de noms de fichiers unifié (app/core/files.py)."""

from __future__ import annotations

from app.core.files import sanitize_filename


def test_sanitize_spaces_and_specials():
    assert sanitize_filename("Hello World!") == "Hello_World"


def test_sanitize_strips_accents_to_ascii():
    assert sanitize_filename("Éléphant café") == "Elephant_cafe"


def test_sanitize_empty_uses_fallback():
    assert sanitize_filename("") == "fichier"
    assert sanitize_filename("!!!") == "fichier"


def test_sanitize_custom_fallback():
    assert sanitize_filename("", fallback="video") == "video"


def test_sanitize_truncates_to_max_length():
    assert len(sanitize_filename("a" * 300)) <= 100
