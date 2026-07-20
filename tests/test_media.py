"""Tests HTTP du convertisseur média (/media/convert, /media/batch).

Couvre le chemin image (Pillow, pas de FFmpeg requis), la garde sur le
paramètre `quality` et le rejet par magic bytes.
"""

from __future__ import annotations

import io
import zipfile

from PIL import Image


def _png(color=(200, 30, 30), size=(8, 8)) -> io.BytesIO:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_convert_png_to_jpeg(client):
    data = {"file": (_png(), "in.png"), "format": "jpeg", "quality": "80"}
    resp = client.post("/media/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert resp.data[:3] == b"\xff\xd8\xff"  # magic JPEG


def test_convert_missing_file_returns_400_json(client):
    resp = client.post("/media/convert")
    assert resp.status_code == 400
    assert resp.is_json


def test_convert_invalid_quality_returns_400(client):
    data = {"file": (_png(), "in.png"), "format": "png", "quality": "pas-un-entier"}
    resp = client.post("/media/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.is_json


def test_convert_rejects_wrong_magic_bytes(client):
    fake = io.BytesIO(b"ceci n'est pas une image")
    data = {"file": (fake, "in.png"), "format": "jpeg"}
    resp = client.post("/media/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_convert_rejects_disallowed_output_format(client):
    data = {"file": (_png(), "in.png"), "format": "exe"}
    resp = client.post("/media/convert", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_batch_images_returns_zip(client):
    data = {
        "files[]": [(_png((0, 200, 0)), "a.png"), (_png((0, 0, 200)), "b.png")],
        "output_format": "JPEG",
        "quality": "70",
    }
    resp = client.post("/media/batch", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(resp.data))
    assert archive.namelist() == ["converted_a.jpg", "converted_b.jpg"]
    assert all(archive.read(name).startswith(b"\xff\xd8\xff") for name in archive.namelist())


def test_batch_invalid_quality_returns_400(client):
    data = {
        "files[]": [(_png(), "a.png")],
        "output_format": "JPEG",
        "quality": "abc",
    }
    resp = client.post("/media/batch", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.is_json


def test_batch_rejects_disallowed_output_format(client):
    data = {
        "files[]": [(_png(), "a.png")],
        "output_format": "TIFF",
    }
    resp = client.post("/media/batch", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.is_json
