"""Convertisseur média : images (Pillow), vidéos et audio (FFmpeg).

Trois familles, trois moteurs :

- images  -> Pillow  (JPG, PNG, WEBP, GIF, BMP, TIFF en entrée)
- vidéos  -> FFmpeg  (MP4, WEBM, MKV, MOV, AVI en entrée)
- audio   -> FFmpeg  (MP3, WAV, FLAC, OGG, M4A en entrée)

Une vidéo convertie vers un format audio voit sa bande-son extraite.

Correctifs de fiabilité (v2.1) :
- l'orientation EXIF des photos est appliquée avant conversion ;
- les GIF/WEBP animés conservent leurs images (save_all) ;
- le paramètre `quality` est réellement appliqué au WEBP ;
- les erreurs Pillow/FFmpeg sont journalisées en entier mais ne
  remontent jamais brutes au client ;
- `-movflags +faststart` pour un MP4 lisible en streaming.
"""

import io
import os
import shutil

# FFmpeg est invoqué sans shell avec un chemin admin et des formats whitelistés.
import subprocess  # nosec B404
import tempfile
import zipfile
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.core.api import json_endpoint
from app.core.rate_limit import limiter
from app.core.uploads import UploadRejected, validate_batch, validate_upload

media_bp = Blueprint("media", __name__)

# Timeouts FFmpeg (secondes) — plafonnent la durée d'une conversion.
VIDEO_TIMEOUT_SECONDS = 300
AUDIO_TIMEOUT_SECONDS = 120
SPOOLED_ZIP_MEMORY_LIMIT = 16 * 1024 * 1024

PIL_IMAGE_FORMATS: dict[str, tuple[str, str]] = {
    "jpg": ("JPEG", "jpg"),
    "jpeg": ("JPEG", "jpg"),
    "png": ("PNG", "png"),
    "webp": ("WEBP", "webp"),
    "gif": ("GIF", "gif"),
}

VIDEO_OUTPUT_FORMATS: frozenset[str] = frozenset({"mp4", "webm"})
AUDIO_OUTPUT_FORMATS: frozenset[str] = frozenset({"mp3", "wav", "flac", "ogg", "m4a"})

# Codec audio par format de sortie ; les formats avec pertes reçoivent -b:a.
AUDIO_CODECS: dict[str, list[str]] = {
    "mp3": ["-c:a", "libmp3lame"],
    "m4a": ["-c:a", "aac"],
    "ogg": ["-c:a", "libvorbis"],
    "flac": ["-c:a", "flac"],
    "wav": ["-c:a", "pcm_s16le"],
}
AUDIO_LOSSY_FORMATS: frozenset[str] = frozenset({"mp3", "m4a", "ogg"})

AUDIO_MIMETYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
}


class InvalidQuality(ValueError):
    """Paramètre `quality` ou `bitrate` non numérique."""


class ConversionError(ValueError):
    """Échec du moteur de conversion. Le message est sûr pour le client."""


def _parse_int_param(raw: object, name: str, default: int, lo: int, hi: int) -> int:
    """Parse et borne un paramètre entier. Lève `InvalidQuality` si non numérique."""
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise InvalidQuality(f"Le paramètre '{name}' doit être un entier.") from None
    return max(lo, min(hi, value))


def _parse_quality(raw: object, default: int = 85) -> int:
    return _parse_int_param(raw, "quality", default, 0, 100)


def _parse_bitrate(raw: object, default: int = 192) -> int:
    return _parse_int_param(raw, "bitrate", default, 32, 320)


@media_bp.route("/")
def index():
    return render_template("media.html")


def media_kind(ext: str) -> str:
    """Famille d'un fichier d'après son extension normalisée."""
    if ext in current_app.config["ALLOWED_VIDEO_EXTENSIONS"]:
        return "video"
    if ext in current_app.config["ALLOWED_AUDIO_EXTENSIONS"]:
        return "audio"
    return "image"


def process_image(img: Image.Image, output_format: str, quality: int = 85) -> io.BytesIO:
    """Convertit une image Pillow vers un buffer prêt à être envoyé."""
    output = io.BytesIO()
    animated = bool(getattr(img, "is_animated", False))

    try:
        if not animated:
            # Applique l'orientation EXIF (photos de téléphone tournées).
            img = ImageOps.exif_transpose(img)

        save_kwargs: dict = {"format": output_format, "optimize": True}

        if output_format == "JPEG":
            if img.mode not in ("RGB", "L", "CMYK"):
                img = img.convert("RGB")
            save_kwargs["quality"] = quality
        elif output_format == "WEBP":
            save_kwargs["quality"] = quality
            if animated:
                save_kwargs["save_all"] = True
        elif output_format == "GIF" and animated:
            save_kwargs["save_all"] = True

        img.save(output, **save_kwargs)
        output.seek(0)
        return output
    except Image.DecompressionBombError:
        raise
    except Exception as exc:
        current_app.logger.error("Erreur Pillow (%s): %s", output_format, exc)
        raise ConversionError(
            "La conversion de l'image a échoué. Le fichier est peut-être corrompu."
        ) from exc


def _quality_to_crf(quality: int, codec: str = "libx264") -> int:
    """Map quality (0-100, plus haut = meilleure qualité) vers un CRF FFmpeg.

    - libx264 : CRF ∈ [15, 32] (par défaut 23)
    - libvpx-vp9 : CRF ∈ [20, 40] (par défaut 30)
    """
    quality = max(0, min(100, quality))
    if codec == "libvpx-vp9":
        return 40 - int((quality / 100) * 20)
    return 32 - int((quality / 100) * 17)


def _ffmpeg_path() -> str:
    """Chemin FFmpeg résolu au boot par config.get_ffmpeg_path()."""
    ffmpeg_path = current_app.config.get("FFMPEG_PATH")
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        raise ConversionError("FFmpeg n'est pas disponible sur cette instance.")
    return ffmpeg_path


def _run_ffmpeg(command: list[str], timeout: int, label: str) -> None:
    """Exécute FFmpeg avec timeout. Journalise tout, ne divulgue rien."""
    current_app.logger.info("Commande FFmpeg (%s): %s", label, " ".join(command))
    try:
        subprocess.run(  # nosec B603
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        minutes = timeout // 60
        current_app.logger.error("Timeout FFmpeg (%s, %s min)", label, minutes)
        raise ConversionError(
            f"La conversion a pris trop de temps (limite : {minutes} minutes)."
        ) from None
    except subprocess.CalledProcessError as exc:
        # stderr complet dans les logs ; message générique côté client.
        current_app.logger.error("Erreur FFmpeg (%s): %s", label, exc.stderr)
        raise ConversionError(
            "La conversion a échoué. Le fichier est peut-être corrompu ou son codec "
            "n'est pas pris en charge."
        ) from exc


def process_video(input_path: str, output_path: str, quality: int = 85) -> str:
    """Conversion vidéo avec FFmpeg. `quality` ∈ [0, 100]."""
    command = [_ffmpeg_path(), "-i", input_path, "-y"]

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
                "-movflags",
                "+faststart",
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
    _run_ffmpeg(command, VIDEO_TIMEOUT_SECONDS, f"vidéo -> {output_format}")

    if not os.path.exists(output_path):
        raise ConversionError("La conversion n'a pas généré de fichier de sortie.")

    current_app.logger.info(
        "Conversion vidéo terminée - taille: %s bytes", os.path.getsize(output_path)
    )
    return output_path


def process_audio(input_path: str, output_path: str, bitrate: int = 192) -> str:
    """Conversion audio (ou extraction de la bande-son d'une vidéo) via FFmpeg."""
    output_format = os.path.splitext(output_path)[1][1:]
    codec_args = AUDIO_CODECS.get(output_format)
    if codec_args is None:
        raise ConversionError(f"Format audio non pris en charge : .{output_format}")

    # -vn : ignore toute piste vidéo (no-op pour une source audio pure).
    command = [_ffmpeg_path(), "-i", input_path, "-y", "-vn", *codec_args]
    if output_format in AUDIO_LOSSY_FORMATS:
        command.extend(["-b:a", f"{bitrate}k"])
    command.append(output_path)

    _run_ffmpeg(command, AUDIO_TIMEOUT_SECONDS, f"audio -> {output_format}")

    if not os.path.exists(output_path):
        raise ConversionError("La conversion n'a pas généré de fichier de sortie.")

    current_app.logger.info(
        "Conversion audio terminée - taille: %s bytes", os.path.getsize(output_path)
    )
    return output_path


def _convert_with_ffmpeg(file, input_filename: str, output_format: str, runner) -> object:
    """Sauvegarde l'upload en temporaire, convertit, renvoie le fichier.

    `runner(input_path, output_path)` effectue la conversion.
    Le répertoire temporaire est nettoyé à la fermeture de la réponse.
    """
    temp_root = current_app.config["TEMP_FOLDER"]
    os.makedirs(temp_root, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="media_", dir=temp_root)
    input_path = os.path.join(temp_dir, input_filename)
    output_path = os.path.join(temp_dir, f"converted.{output_format}")

    try:
        file.save(input_path)
        result_path = runner(input_path, output_path)
        response = send_file(
            result_path,
            mimetype=AUDIO_MIMETYPES.get(output_format),
            as_attachment=True,
            download_name=f"converted_{Path(input_filename).stem}.{output_format}",
        )
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@media_bp.route("/convert", methods=["POST"])
@json_endpoint
@limiter.limit("30 per minute")
def convert_media():
    if "file" not in request.files:
        return jsonify({"error": "Fichier manquant"}), 400

    file = request.files["file"]

    try:
        source_ext = validate_upload(file, current_app.config["ALLOWED_MEDIA_EXTENSIONS"])
    except UploadRejected as exc:
        return jsonify({"error": str(exc)}), 400

    input_filename = secure_filename(file.filename) or "media"
    output_format = request.form.get("format", "").lower()
    if output_format not in current_app.config["ALLOWED_MEDIA_EXTENSIONS"]:
        return jsonify({"error": f"Format de sortie non autorisé : .{output_format}"}), 400

    try:
        quality = _parse_quality(request.form.get("quality"))
        bitrate = _parse_bitrate(request.form.get("bitrate"))
    except InvalidQuality as exc:
        return jsonify({"error": str(exc)}), 400

    kind = media_kind(source_ext)

    try:
        if kind == "image":
            image_format = PIL_IMAGE_FORMATS.get(output_format)
            if not image_format:
                return jsonify(
                    {"error": "Une image ne peut être convertie que vers JPG, PNG, WEBP ou GIF."}
                ), 400

            pil_format, output_extension = image_format
            try:
                with Image.open(file.stream) as image:
                    output = process_image(image, pil_format, quality)
            except UnidentifiedImageError:
                return jsonify({"error": "Fichier image illisible ou corrompu."}), 400
            except Image.DecompressionBombError:
                return jsonify(
                    {"error": "Image refusée : dimensions démesurées une fois décompressée."}
                ), 400

            return send_file(
                output,
                mimetype=(
                    "image/jpeg" if output_extension == "jpg" else f"image/{output_extension}"
                ),
                as_attachment=True,
                download_name=f"converted_{Path(input_filename).stem}.{output_extension}",
            )

        if kind == "video":
            if output_format in VIDEO_OUTPUT_FORMATS:
                return _convert_with_ffmpeg(
                    file,
                    input_filename,
                    output_format,
                    lambda src, dst: process_video(src, dst, quality),
                )
            if output_format in AUDIO_OUTPUT_FORMATS:
                # Extraction de la bande-son.
                return _convert_with_ffmpeg(
                    file,
                    input_filename,
                    output_format,
                    lambda src, dst: process_audio(src, dst, bitrate),
                )
            return jsonify(
                {"error": "Une vidéo se convertit vers MP4 ou WEBM, ou vers un format audio."}
            ), 400

        # kind == "audio"
        if output_format in AUDIO_OUTPUT_FORMATS:
            return _convert_with_ffmpeg(
                file,
                input_filename,
                output_format,
                lambda src, dst: process_audio(src, dst, bitrate),
            )
        return jsonify(
            {"error": "Un fichier audio se convertit vers MP3, WAV, FLAC, OGG ou M4A."}
        ), 400

    except ConversionError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        current_app.logger.error("Erreur de conversion inattendue: %s", exc, exc_info=True)
        return jsonify({"error": "Erreur interne pendant la conversion."}), 500


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
