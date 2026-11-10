"""Downloads model files that are too large to keep in git. Verifies SHA-256 before installing.

Usage:  python scripts/fetch_models.py
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "app" / "assets"
MODELS = [
    {
        "name": "LBF 68-point facial landmark model (OpenCV Facemark, BSD licence, GSoC 2017)",
        "url": "https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml",
        "path": ASSETS / "lbfmodel.yaml",
        "sha256": "70dd8b1657c42d1595d6bd13d97d932877b3bed54a95d3c4733a0f740d1fd66b",
    },
    {
        "name": "YuNet face detector 2023mar (OpenCV Zoo, MIT licence)",
        # raw.githubusercontent.com serves only the Git LFS pointer for this file; media.githubusercontent.com serves the blob
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"
               "face_detection_yunet_2023mar.onnx",
        "path": ASSETS / "face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for m in MODELS:
        target: Path = m["path"]
        if target.exists() and sha256(target) == m["sha256"]:
            print(f"ok       {target.name} (already present)")
            continue
        print(f"download {target.name} ...")
        tmp = target.with_suffix(".part")
        urllib.request.urlretrieve(m["url"], tmp)
        if sha256(tmp) != m["sha256"]:
            tmp.unlink(missing_ok=True)
            print(f"ERROR: checksum mismatch for {target.name}; file discarded.", file=sys.stderr)
            return 1
        tmp.replace(target)
        print(f"installed {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
