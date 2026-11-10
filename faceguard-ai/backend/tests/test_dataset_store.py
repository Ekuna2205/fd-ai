"""Dataset store: pure logic + real image bytes (synthetic noise images made inside the test; no external data)."""
import io
import sys
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parents[2] / "ai"))
from app.services import dataset_store as ds  # noqa: E402

A, B = "user-a", "user-b"


def img(seed: int, ext=".png", side=96) -> bytes:
    arr = np.random.default_rng(seed).integers(0, 255, (side, side, 3), dtype=np.uint8)
    return cv2.imencode(ext, arr)[1].tobytes()


def validator(name, data):
    """Stand-in with the same contract as the API's validator (magic bytes + decode)."""
    kind = "jpeg" if data.startswith(b"\xff\xd8\xff") else "png" if data.startswith(b"\x89PNG") else None
    if kind is None:
        raise ds.DatasetError("The file content does not match a supported format.")
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise ds.DatasetError("corrupt")
    return kind, im.shape[1], im.shape[0]


def store():
    return ds.DatasetStore(tempfile.mkdtemp(prefix="fg-ds-"))


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return e
    raise AssertionError(f"{exc.__name__} not raised")


def test_create_list_and_name_rules():
    s = store()
    d = s.create(A, "  My set ", "desc")
    assert d["name"] == "My set" and d["images"] == 0
    assert [x["id"] for x in s.list(A)] == [d["id"]] and s.list(B) == []
    raises(ds.DatasetConflict, s.create, A, "my SET")          # duplicate name, case-insensitive
    assert s.create(B, "My set")["id"] != d["id"]               # other users may reuse the name
    raises(ds.DatasetError, s.create, A, "   ")
    raises(ds.DatasetError, s.create, A, "x" * 81)


def test_other_users_cannot_see_or_touch_a_dataset():
    s = store(); d = s.create(A, "private"); i = d["id"]
    sha = s.add_image(A, i, "a.png", img(1), validator, "REAL")["sha256"]
    for call in (lambda: s.get(B, i), lambda: s.stats(B, i), lambda: s.validate(B, i), lambda: s.delete(B, i),
                 lambda: s.export_zip(B, i), lambda: s.add_image(B, i, "b.png", img(2), validator),
                 lambda: s.update_image(B, i, sha, label="FAKE"), lambda: s.remove_image(B, i, sha),
                 lambda: s.read_image(B, i, sha)):
        assert str(raises(ds.DatasetNotFound, call)) == "Dataset not found."   # same message as a missing id
    assert s.get(A, i)["images"] == 1                                         # nothing was changed


def test_ids_cannot_traverse_the_filesystem():
    s = store()
    for bad in ("../x", "..", "a" * 31, "A" * 32, "", "0" * 32 + "/../..", "%2e%2e"):
        raises(ds.DatasetNotFound, s.get, A, bad)
    d = s.create(A, "t")
    for bad in ("../../etc/passwd", "x", "A" * 64, ""):
        raises(ds.DatasetNotFound, s.update_image, A, d["id"], bad, label="REAL")


def test_add_validates_dedupes_and_ignores_client_filenames_for_paths():
    s = store(); i = s.create(A, "t")["id"]
    r = s.add_image(A, i, "../../evil name.png", img(1), validator, "REAL", identity="p001", group="cam1")
    assert r["original_name"] == "evil name.png" and r["ext"] == ".png" and len(r["sha256"]) == 64
    files = [p.name for p in (Path(s.root) / i / "images").iterdir()]
    assert files == [f"{r['sha256']}.png"]                                     # content-hash name only
    raises(ds.DatasetConflict, s.add_image, A, i, "copy.png", img(1), validator)  # exact duplicate
    raises(ds.DatasetError, s.add_image, A, i, "x.png", b"MZ\x90\x00 not an image", validator)
    raises(ds.DatasetError, s.add_image, A, i, "x.png", img(9), validator, label="MAYBE")
    raises(ds.DatasetError, s.add_image, A, i, "x.png", img(9), validator, identity="Jane Doe!")  # no free-text names
    assert s.get(A, i)["images"] == 1                                          # failures stored nothing
    assert not list((Path(s.root) / i / "images").glob("*.part"))


def test_limits_are_enforced():
    s = ds.DatasetStore(tempfile.mkdtemp(), max_datasets_per_user=1, max_images=2, max_dataset_bytes=10 << 20)
    i = s.create(A, "one")["id"]
    raises(ds.DatasetError, s.create, A, "two")
    s.add_image(A, i, "a.png", img(1), validator); s.add_image(A, i, "b.png", img(2), validator)
    assert "limit" in str(raises(ds.DatasetError, s.add_image, A, i, "c.png", img(3), validator))


def test_labels_update_filter_and_pagination():
    s = store(); i = s.create(A, "t")["id"]
    shas = [s.add_image(A, i, f"{n}.png", img(n), validator)["sha256"] for n in range(5)]
    s.update_image(A, i, shas[0], label="REAL"); s.update_image(A, i, shas[1], label="FAKE", identity="p1")
    s.update_image(A, i, shas[1], label=None)                                   # clearing is allowed
    got = s.get(A, i, label="REAL"); assert got["total_filtered"] == 1 and got["items"][0]["sha256"] == shas[0]
    assert s.get(A, i, label="UNLABELED")["total_filtered"] == 4
    page = s.get(A, i, offset=2, limit=2); assert len(page["items"]) == 2 and page["total_filtered"] == 5
    raises(ds.DatasetError, s.get, A, i, label="BOGUS")
    raises(ds.DatasetError, s.update_image, A, i, shas[0], label="REAL?")


def test_stats_and_validation_report_real_problems_not_invented_ones():
    s = store(); i = s.create(A, "t")["id"]
    v = s.validate(A, i); assert not v["ready"] and any("at least 20 real" in p for p in v["problems"])
    for n in range(20):
        s.add_image(A, i, f"r{n}.png", img(n), validator, "REAL", identity=f"p{n % 4}")
    for n in range(20):
        s.add_image(A, i, f"f{n}.jpg", img(100 + n, ".jpg"), validator, "FAKE", identity=f"p{n % 4}")
    st = s.stats(A, i)
    assert st["labels"] == {"REAL": 20, "FAKE": 20, "UNLABELED": 0} and st["identities"] == 4
    assert st["identities_by_label"] == {"REAL": 4, "FAKE": 4} and st["min_side_px"] == 96
    v = s.validate(A, i); assert v["ready"] and v["problems"] == [] and v["warnings"] == []
    s.add_image(A, i, "u.png", img(500, side=64), validator)                   # unlabeled + no identity
    v = s.validate(A, i); assert not v["ready"] and any("no REAL/FAKE label" in p for p in v["problems"])
    assert any("identity-disjoint" in w for w in v["warnings"])


def test_validation_detects_tampered_and_missing_files():
    s = store(); i = s.create(A, "t")["id"]
    a = s.add_image(A, i, "a.png", img(1), validator, "REAL")["sha256"]
    b = s.add_image(A, i, "b.png", img(2), validator, "REAL")["sha256"]
    (Path(s.root) / i / "images" / f"{a}.png").write_bytes(b"tampered")
    (Path(s.root) / i / "images" / f"{b}.png").unlink()
    probs = s.validate(A, i, min_per_class=0)["problems"]
    assert any("hash mismatch" in p for p in probs) and any("missing" in p for p in probs)


def test_imbalance_warning():
    s = store(); i = s.create(A, "t")["id"]
    for n in range(25):
        s.add_image(A, i, f"r{n}.png", img(n), validator, "REAL", identity=f"p{n}")
    for n in range(5):
        s.add_image(A, i, f"f{n}.png", img(100 + n), validator, "FAKE", identity=f"p{n}")
    assert any("imbalanced" in w for w in s.validate(A, i, min_per_class=5)["warnings"])


def test_remove_image_and_secure_delete_wipe_files():
    s = store(); i = s.create(A, "t")["id"]
    sha = s.add_image(A, i, "a.png", img(1), validator, "REAL")["sha256"]
    s.add_image(A, i, "b.png", img(2), validator, "FAKE")
    s.remove_image(A, i, sha)
    assert s.get(A, i)["images"] == 1 and not (Path(s.root) / i / "images" / f"{sha}.png").exists()
    assert s.delete(A, i) == 1 and not (Path(s.root) / i).exists() and s.list(A) == []
    raises(ds.DatasetNotFound, s.get, A, i)


def test_export_is_loadable_by_the_training_pipeline_and_skips_unlabeled():
    from faceguard_ai import data as aidata                                    # the existing Phase 5 loader
    s = store(); i = s.create(A, "t")["id"]
    for n in range(3):
        s.add_image(A, i, f"r{n}.png", img(n), validator, "REAL", identity=f"p{n}")
        s.add_image(A, i, f"f{n}.jpg", img(50 + n, ".jpg"), validator, "FAKE", identity=f"p{n}", group="screen")
    s.add_image(A, i, "u.png", img(999), validator)
    blob, info = s.export_zip(A, i)
    assert info == {"exported": 6, "skipped_unlabeled": 1}
    with tempfile.TemporaryDirectory() as d:
        zipfile.ZipFile(io.BytesIO(blob)).extractall(d)
        samples, problems = aidata.load_manifest(Path(d) / "manifest.csv", min_per_class=3)
        assert problems == [] and len(samples) == 6
        assert sorted(x.label for x in samples) == [0, 0, 0, 1, 1, 1]
        assert {x.identity for x in samples} == {"p0", "p1", "p2"} and all(x.sha256 for x in samples)
