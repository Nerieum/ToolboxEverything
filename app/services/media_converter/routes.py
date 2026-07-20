import io
import os
import shutil

# FFmpeg est invoqué sans shell avec un chemin admin et des formats whitelistés.
import subprocess  # nosec B404
import tempfile
import zipfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

from app.core.api import json_endpoint
from app.core.rate_limit import limiter
from app.core.uploads import UploadRejected, validate_batch, validate_upload

media_bp = Blueprint("media", __name__)

# Timeout FFmpeg (secondes) — plafonne la durée d'une conversion vidéo.
VIDEO_TIMEOUT_SECONDS = 180
SPOOLED_ZIP_MEMORY_LIMIT = 16 * 1024 * 1024

PIL_IMAGE_FORMATS: dict[str, tuple[str, str]] = {
    "jpg": ("JPEG", "jpg"),
    "jpeg": ("JPEG", "jpg"),
    "png": ("PNG", "png"),
    "webp": ("WEBP", "webp"),
    "gif": ("GIF", "gif"),
}


class InvalidQuality(ValueError):
    """Paramètre `quality` non numérique."""


def _parse_quality(raw: object, default: int = 85) -> int:
    """Parse et borne `quality` ∈ [0, 100]. Lève `InvalidQuality` si non numérique."""
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise InvalidQuality("Le paramètre 'quality' doit être un entier.") from None
    return max(0, min(100, value))


@media_bp.route("/")
def index():
    return render_template("media.html")


def is_video(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_VIDEO_EXTENSIONS"]
    )


def process_image(img: Image.Image, output_format: str, quality: int = 85) -> io.BytesIO:
    """Convertit une image Pillow vers un buffer prêt à être envoyé."""
    output = io.BytesIO()

    try:
        if output_format == "JPEG":
            if img.mode not in ("RGB", "L", "CMYK"):
                img = img.convert("RGB")
            img.save(output, format=output_format, quality=quality, optimize=True)
        else:
            img.save(output, format=output_format, optimize=True)

        output.seek(0)
        return output
    except Exception as exc:
        raise ValueError(f"Erreur lors du traitement de l'image: {exc}") from exc


def _quality_to_crf(quality: int, codec: str = "libx264") -> int:
    """Map quality (0-100, plus haut = meilleure qualité) vers un CRF FFmpeg.

    - libx264 : CRF ∈ [15, 32] (par défaut 23)
    - libvpx-vp9 : CRF ∈ [20, 40] (par défaut 30)
    """
    quality = max(0, min(100, quality))
    if codec == "libvpx-vp9":
        return 40 - int((quality / 100) * 20)
    return 32 - int((quality / 100) * 17)


def process_video(input_path: str, output_path: str, quality: int = 85) -> str:
    """Conversion vidéo avec FFmpeg. `quality` ∈ [0, 100]."""
    try:
        # FFmpeg : source unique = app.config["FFMPEG_PATH"], résolu au boot
        # par config.get_ffmpeg_path() dans la factory.
        ffmpeg_path = current_app.config.get("FFMPEG_PATH")
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            raise ValueError("FFmpeg n'est pas disponible")

        command = [ffmpeg_path, "-i", input_path, "-y"]

        output_format = os.path.splitext(output_path)[1][1:]
        if output_format == "mp4":
            crf = _quality_to_crf(quality, "libx264")
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    str(crf),
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                ]
            )
        elif output_format == "webm":
            crf = _quality_to_crf(quality, "libvpx-vp9")
            command.extend(
                [
                    "-c:v",
                    "libvpx-vp9",
                    "-crf",
                    str(crf),
                    "-b:v",
                    "0",
                    "-c:a",
                    "libopus",
                    "-deadline",
                    "good",
                    "-cpu-used",
                    "1",
                ]
            )

        command.append(output_path)

        current_app.logger.info("Commande FFmpeg: %s", " ".join(command))
        current_app.logger.info("Début conversion - timeout: %s secondes", VIDEO_TIMEOUT_SECONDS)

        subprocess.run(  # nosec B603
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=VIDEO_TIMEOUT_SECONDS,
        )

        if not os.path.exists(output_path):
            raise ValueError("La conversion n'a pas généré de fichier de sortie")

        output_size = os.path.getsize(output_path)
        current_app.logger.info("Conversion terminée avec succès - taille: %s bytes", output_size)

        return output_path

    except subprocess.TimeoutExpired:
        minutes = VIDEO_TIMEOUT_SECONDS // 60
        current_app.logger.error("Timeout de conversion FFmpeg (%s min)", minutes)
        raise ValueError(
            f"La conversion a pris trop de temps (limite: {minutes} minutes)."
        ) from None
    except subprocess.CalledProcessError as exc:
        current_app.logger.error("Erreur FFmpeg: %s", exc.stderr)
        raise ValueError(f"Erreur lors de la conversion: {exc.stderr}") from exc
    except Exception as exc:
        current_app.logger.error("Erreur: %s", exc)
        raise


@media_bp.route("/convert", methods=["POST"])
@json_endpoint
@limiter.limit("10 per minute")
def convert_media():
    if "file" not in request.files:
        return jsonify({"error": "Fichier manquant"}), 400

    file = request.files["file"]

    try:
        validate_upload(file, current_app.config["ALLOWED_MEDIA_EXTENSIONS"])
    except UploadRejected as exc:
        return jsonify({"error": str(exc)}), 400

    input_filename = secure_filename(file.filename) or "media"
    output_format = request.form.get("format", "").lower()
    if output_format not in current_app.config["ALLOWED_MEDIA_EXTENSIONS"]:
        return jsonify({"error": f"Format de sortie non autorisé : .{output_format}"}), 400
    try:
        quality = _parse_quality(request.form.get("quality"))
    except InvalidQuality as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        if not is_video(file.filename):
            image_format = PIL_IMAGE_FORMATS.get(output_format)
            if not image_format:
                return jsonify({"error": f"Format image non autorisé : .{output_format}"}), 400

            pil_format, output_extension = image_format
            with Image.open(file.stream) as image:
                output = process_image(image, pil_format, quality)
            return send_file(
                output,
                mimetype=(
                    "image/jpeg" if output_extension == "jpg" else f"image/{output_extension}"
                ),
                as_attachment=True,
                download_name=f"converted_{Path(input_filename).stem}.{output_extension}",
            )

        temp_root = current_app.config["TEMP_FOLDER"]
        os.makedirs(temp_root, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix="media_", dir=temp_root)
        input_path = os.path.join(temp_dir, input_filename)
        output_path = os.path.join(temp_dir, f"converted.{output_format}")

        try:
            file.save(input_path)
            current_app.logger.info("Début conversion vidéo: %s -> %s", input_path, output_path)
            result_path = process_video(input_path, output_path, quality)
            response = send_file(
                result_path,
                as_attachment=True,
                download_name=f"converted_{Path(input_filename).stem}.{output_format}",
            )
            response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
            return response
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    except Exception as exc:
        current_app.logger.error("Erreur de conversion: %s", exc)
        return jsonify({"error": str(exc)}), 500


@media_bp.route("/batch", methods=["POST"])
@json_endpoint
@limiter.limit("3 per minute")
def batch_process():
    """Traite plusieurs images en batch (images uniquement)."""
    if "files[]" not in request.files:
        return jsonify({"error": "Aucun fichier transmis"}), 400

    try:
        validated = validate_batch(
            request.files.getlist("files[]"),
            current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
        )
    except UploadRejected as exc:
        return jsonify({"error": str(exc)}), 400

    requested_format = request.form.get("output_format", "JPEG").lower()
    image_format = PIL_IMAGE_FORMATS.get(requested_format)
    if not image_format:
        return jsonify({"error": f"Format image non autorisé : .{requested_format}"}), 400
    output_format, output_extension = image_format
    try:
        quality = _parse_quality(request.form.get("quality"))
    except InvalidQuality as exc:
        return jsonify({"error": str(exc)}), 400

    # Le fichier reste ouvert le temps du streaming, puis est fermé par
    # response.call_on_close plus bas.
    archive_file = tempfile.SpooledTemporaryFile(  # noqa: SIM115
        max_size=SPOOLED_ZIP_MEMORY_LIMIT,
        mode="w+b",
    )
    with zipfile.ZipFile(archive_file, "w") as archive:
        archive_names: set[str] = set()
        for file, _ext in validated:
            try:
                with Image.open(file.stream) as image:
                    processed = process_image(image, output_format, quality)
                source_name = secure_filename(file.filename) or "image"
                filename = f"converted_{Path(source_name).stem}.{output_extension}"
                suffix = 2
                while filename in archive_names:
                    filename = f"converted_{Path(source_name).stem}_{suffix}.{output_extension}"
                    suffix += 1
                archive_names.add(filename)
                archive.writestr(filename, processed.getvalue())
            except Image.DecompressionBombError:
                current_app.logger.warning("Image bomb refusée: %s", file.filename)
                continue
            except Exception as exc:
                current_app.logger.error("Erreur sur %s: %s", file.filename, exc)
                continue

    archive_file.seek(0)
    response = send_file(
        archive_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="processed_images.zip",
    )
    response.call_on_close(archive_file.close)
    return response
