"""API messages follow Accept-Language (mn / en). English stays the default and the source of truth."""
from app.core import i18n
from app.locales import mn
from tests.conftest import files, jpeg, portrait

MN = {"Accept-Language": "mn"}


def test_accept_language_parsing():
    assert i18n.parse_accept_language("mn-MN,mn;q=0.9,en;q=0.5") == "mn"
    assert i18n.parse_accept_language("en-US,en;q=0.9") == "en"
    assert i18n.parse_accept_language("de-DE") == "en"
    assert i18n.parse_accept_language(None) == "en"


def test_sentence_by_sentence_with_patterns_and_fallback():
    text = "One face was detected. Quality issues: face size, lighting. The model's bona fide score is 4.7% (threshold 0.50), which indicates a presentation attack."
    out = i18n.tr(text, "mn")
    assert out.startswith("Нэг нүүр илэрлээ. Чанарын асуудал: нүүрний хэмжээ, гэрэлтүүлэг.")
    assert "4.7%" in out and "0.50" in out and "One face" not in out
    assert i18n.tr("A brand new sentence.", "mn") == "A brand new sentence."  # unknown -> English, never an error
    assert i18n.tr(text, "en") == text


def test_every_pattern_template_is_well_formed():
    for rx, tpl in mn.PATTERNS:
        if isinstance(tpl, str):
            assert tpl.count("{") == tpl.count("}")
            assert max([int(x) for x in __import__("re").findall(r"\{(\d+)\}", tpl)] or [-1]) < rx.groups


def test_error_messages_are_translated(client):
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong-password-1"}, headers=MN)
    assert r.status_code == 401 and r.json()["detail"] == "Имэйл эсвэл нууц үг буруу байна."
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong-password-1"})
    assert r.json()["detail"] == "Incorrect email or password."
    r = client.post("/api/auth/register", json={"email": "x@example.com"}, headers=MN)
    assert r.status_code == 422 and r.json()["detail"] == "Зарим талбар буруу байна."
    assert any(e["message"] == "Заавал бөглөх талбар" for e in r.json()["errors"])


def test_verification_explanation_and_quality_in_mongolian(client, operator):
    r = client.post("/api/uploads/image", headers={**operator["h"], **MN}, data={"consent": "true"},
                    files=files("a.jpg", jpeg(portrait()), "image/jpeg"))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["explanation"].startswith("Нэг нүүр илэрлээ.")
    assert "Сургасан амьд байдлын модель идэвхгүй" in b["explanation"]
    assert b["liveness"]["reason"] == "Бүртгэлтэй, идэвхтэй амьд байдлын модель алга."
    assert {c["label"] for c in b["quality"]["checks"]} >= {"Нүүрний хэмжээ", "Гэрэлтүүлэг"}


def test_live_guidance_and_challenge_instructions(client, operator):
    r = client.post("/api/face/detect", headers={**operator["h"], **MN}, data={"consent": "true"},
                    files={"image": ("f.jpg", jpeg(portrait()), "image/jpeg")})
    assert r.status_code == 200 and all(any("Ѐ" <= ch <= "ӿ" for ch in g) for g in r.json()["guidance"])
    c = client.post("/api/face/challenge", headers={**operator["h"], **MN}).json()
    assert all(any("Ѐ" <= ch <= "ӿ" for ch in s["instruction"]) for s in c["steps"])
