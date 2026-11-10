"""Media validation and decoding. Never trusts file names or client-declared content types."""
import io
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.errors import AppError

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = {".mp4", ".webm"}
MIME = {"jpeg": "image/jpeg", "png": "image/png", "mp4": "video/mp4", "webm": "video/webm"}
_CHUNK = 1 << 20


def sniff_type(head: bytes) -> str | None:
    """Identify the real container from magic bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[4:8] == b"ftyp":
        return "mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in head[:64].lower():
        return "webm"
    return None


def safe_filename(name: str | None) -> str:
    """For display/audit only: the name is never used to build a filesystem path."""
    base = os.path.basename((name or "upload").replace("\\", "/"))
    return re.sub(r"[^\w.\- ]", "_", base)[:120] or "upload"


def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    while chunk := file.file.read(_CHUNK):
        data += chunk
        if len(data) > max_bytes:
            raise AppError(f"File is too large. The limit is {max_bytes // (1 << 20)} MB.", 413)
    if not data:
        raise AppError("The file is empty.", 422)
    return bytes(data)


def validate(kind: str, filename: str | None, data: bytes) -> str:
    """kind: 'image' or 'video'. Returns the sniffed type ('jpeg', 'png', 'mp4', 'webm')."""
    ext = Path(filename or "").suffix.lower()
    allowed_ext = IMAGE_EXT if kind == "image" else VIDEO_EXT
    if ext not in allowed_ext:
        raise AppError(f"Unsupported file extension. Allowed: {', '.join(sorted(allowed_ext))}.", 415)
    sniffed = sniff_type(data[:64])
    allowed_types = {"jpeg", "png"} if kind == "image" else {"mp4", "webm"}
    if sniffed not in allowed_types:
        raise AppError("The file content does not match a supported format.", 415)
    if (ext in {".jpg", ".jpeg"} and sniffed != "jpeg") or (ext == ".png" and sniffed != "png") \
            or (ext == ".mp4" and sniffed != "mp4") or (ext == ".webm" and sniffed != "webm"):
        raise AppError("The file extension does not match its content.", 415)
    return sniffed


def decode_image(data: bytes) -> np.ndarray:
    """Returns a BGR uint8 array. Rejects corrupt files and decompression bombs before decoding pixels."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
            if w * h > get_settings().max_image_pixels:
                raise AppError(f"Image dimensions are too large ({w}x{h}).", 413)
            if min(w, h) < 64:
                raise AppError("Image is too small to analyse (minimum 64 px).", 422)
            im.load()
            im = ImageOps.exif_transpose(im).convert("RGB")
            return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise AppError("The image is corrupted or cannot be read.", 422) from None


def secure_delete(path: str) -> None:
    """Best-effort: overwrite with zeros, then unlink. Cannot defeat SSD wear-levelling or journaling."""
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(b"\x00" * size)
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


@contextmanager
def temp_media(data: bytes, suffix: str):
    """Writes bytes to a temp file (OpenCV needs a path for video) and always securely removes it."""
    directory = get_settings().upload_temp_dir or None
    fd, path = tempfile.mkstemp(suffix=suffix, dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield path
    finally:
        secure_delete(path)
