import os

import pytest

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.face import media
from tests.conftest import jpeg, noise, png


def test_sniff_recognises_real_containers():
    assert media.sniff_type(jpeg(noise())[:64]) == "jpeg"
    assert media.sniff_type(png(noise())[:64]) == "png"
    assert media.sniff_type(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20) == "mp4"
    assert media.sniff_type(b"\x1a\x45\xdf\xa3" + b"\x42\x82webm" + b"\x00" * 20) == "webm"
    assert media.sniff_type(b"MZ\x90\x00 this is an executable") is None


@pytest.mark.parametrize("name,data,status", [
    ("a.jpg", b"MZ\x90\x00" + b"\x00" * 100, 415),                  # executable renamed to .jpg
    ("a.gif", b"GIF89a" + b"\x00" * 100, 415),                       # unsupported extension
    ("a.png", b"\xff\xd8\xff" + b"\x00" * 100, 415),                 # JPEG content with .png name
])
def test_validate_rejects_spoofed_or_unsupported_files(name, data, status):
    with pytest.raises(AppError) as e:
        media.validate("image", name, data)
    assert e.value.status_code == status


def test_validate_accepts_matching_extension_and_content():
    assert media.validate("image", "x.JPEG", jpeg(noise())) == "jpeg"
    assert media.validate("image", "x.png", png(noise())) == "png"


def test_decode_rejects_corrupt_tiny_and_oversized_images(monkeypatch):
    with pytest.raises(AppError) as e:
        media.decode_image(jpeg(noise())[:300])  # truncated
    assert e.value.status_code == 422
    with pytest.raises(AppError):
        media.decode_image(png(noise(32, 32)))  # below 64 px
    monkeypatch.setattr(get_settings(), "max_image_pixels", 100_000)
    with pytest.raises(AppError) as e:
        media.decode_image(png(noise(480, 640)))
    assert e.value.status_code == 413


def test_read_limited_enforces_size_and_rejects_empty():
    import io
    from fastapi import UploadFile
    with pytest.raises(AppError) as e:
        media.read_limited(UploadFile(io.BytesIO(b"x" * 2000), filename="a.jpg"), 1000)
    assert e.value.status_code == 413
    with pytest.raises(AppError):
        media.read_limited(UploadFile(io.BytesIO(b""), filename="a.jpg"), 1000)


def test_filename_is_sanitised_never_a_path():
    assert media.safe_filename("../../etc/passwd") == "passwd"
    assert media.safe_filename("C:\\Users\\me\\face<1>.jpg") == "face_1_.jpg"
    assert media.safe_filename(None) == "upload"


def test_temp_media_is_zeroed_and_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_temp_dir", str(tmp_path))
    with media.temp_media(b"secret-bytes", ".mp4") as path:
        assert os.path.exists(path)
    assert os.listdir(tmp_path) == []
    with pytest.raises(RuntimeError), media.temp_media(b"x", ".mp4"):  # cleanup also happens on errors
        raise RuntimeError
    assert os.listdir(tmp_path) == []
