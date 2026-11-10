"""Every TypeScript interface the UI relies on must have exactly the keys the real API returns.
The TS files are parsed (not copied), so renaming a field on either side fails here instead of breaking a page."""
import re
from pathlib import Path

import pytest

from tests.conftest import add_evaluation, add_model, add_result, jpeg, portrait

TYPES = Path(__file__).resolve().parents[2] / "frontend/src/types"
pytestmark = pytest.mark.skipif(not TYPES.exists(), reason="frontend sources not available")


def ts_keys(file: str, name: str) -> set[str]:
    """Top-level property names of `export interface <name> [extends Base] { ... }`."""
    src = (TYPES / file).read_text()
    m = re.search(rf"export interface {name}(?:\s+extends\s+(\w+))?\s*\{{", src)
    assert m, f"{name} not found in {file}"
    depth, i, body = 1, m.end(), []
    while depth:
        ch = src[i]
        depth += ch in "{[(" and 1 or (ch in "}])" and -1 or 0)
        body.append(ch if depth else "")
        i += 1
    text, keys, level = "".join(body), set(), 0
    top = []
    for ch in text:  # keep only depth-0 characters so nested object members are ignored
        if ch in "{[(<":
            level += 1
        elif ch in "}])>":
            level -= 1
        elif level == 0:
            top.append(ch)
    for part in re.split(r"[;\n]", "".join(top)):
        k = re.match(r"\s*(\w+)\??\s*:", part)
        if k:
            keys.add(k.group(1))
    if m.group(1):
        keys |= ts_keys(file, m.group(1))
    return keys


def same(api_obj: dict, file: str, name: str):
    assert set(api_obj) == ts_keys(file, name), f"{name}: API {sorted(set(api_obj) ^ ts_keys(file, name))} differ from types/{file}"


def test_auth_contract(client, admin):
    body = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Correct-horse-9"}).json()
    same(body, "auth.ts", "AuthResponse")
    same(body["user"], "auth.ts", "AuthUser")


def test_history_and_verification_contract(client, admin, db):
    r = add_result(db, "FAKE", "PHONE_SCREEN", user_id=admin["user"]["id"], confidence=0.9)
    page = client.get("/api/verifications", headers=admin["h"]).json()
    same(page, "history.ts", "HistoryPage")
    same(page["items"][0], "history.ts", "HistoryItem")
    same(client.get(f"/api/verifications/{r.id}", headers=admin["h"]).json(), "face.ts", "VerificationResult")


def test_report_and_audit_contract(client, admin, db):
    add_result(db, "REAL", user_id=admin["user"]["id"])
    rep = client.get("/api/reports/summary", headers=admin["h"]).json()
    same(rep, "history.ts", "ReportSummary")
    same(rep["series"][0], "history.ts", "SeriesPoint")
    audit = client.get("/api/admin/audit-logs", headers=admin["h"]).json()
    same(audit, "history.ts", "AuditPage")
    same(audit["items"][0], "history.ts", "AuditItem")


def test_model_contract(client, admin, db):
    m = add_model(db, active=False, trained=True)
    add_evaluation(db, m, apcer=0.1, bpcer=0.1, acer=0.1, sample_count=300, report={"identity_disjoint": True})
    same(client.get("/api/models", headers=admin["h"]).json()[0], "models.ts", "ModelInfo")
    detail = client.get(f"/api/models/{m.id}", headers=admin["h"]).json()
    same(detail, "models.ts", "ModelDetail")
    same(detail["evaluations"][0], "models.ts", "Evaluation")


def test_dataset_contract(client, admin):
    ds = client.post("/api/datasets", json={"name": "contract"}, headers=admin["h"]).json()
    same(ds, "datasets.ts", "DatasetSummary")
    up = client.post(f"/api/datasets/{ds['id']}/images", headers=admin["h"], files={"file": ("a.jpg", jpeg(portrait()), "image/jpeg")}, data={"label": "REAL", "identity": "p1"})
    assert up.status_code in (200, 201), up.text
    same(up.json(), "datasets.ts", "DatasetImage")
    same(client.get("/api/datasets", headers=admin["h"]).json()[0], "datasets.ts", "DatasetSummary")
    page = client.get(f"/api/datasets/{ds['id']}", headers=admin["h"]).json()
    same(page, "datasets.ts", "DatasetPage")
    same(page["items"][0], "datasets.ts", "DatasetImage")
    val = client.get(f"/api/datasets/{ds['id']}/validation", headers=admin["h"]).json()
    same(val, "datasets.ts", "DatasetValidation")
    same(val["stats"], "datasets.ts", "DatasetStats")


def test_face_capabilities_and_challenge_contract(client, operator):
    same(client.get("/api/face/capabilities", headers=operator["h"]).json(), "face.ts", "Capabilities")
    same(client.post("/api/face/challenge", headers=operator["h"]).json(), "challenge.ts", "Challenge")


def test_the_parser_itself_detects_drift():
    assert ts_keys("auth.ts", "AuthUser") == {"id", "email", "full_name", "role", "is_active", "created_at", "last_login_at"}
    assert {"evaluations", "latest_evaluation"} <= ts_keys("models.ts", "ModelDetail")  # `extends` is followed
    with pytest.raises(AssertionError):
        same({"id": 1, "extra_field": 2}, "auth.ts", "AuthUser")
