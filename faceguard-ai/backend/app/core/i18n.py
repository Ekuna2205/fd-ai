"""Server-side translation of user-facing messages (English -> Mongolian).

The request language comes from `Accept-Language` (the web app sends its UI language). Messages are written in English
in the code and translated *sentence by sentence* at the API boundary with `tr()`:
  * exact sentences:   app/locales/mn.py SENTENCES
  * sentences with numbers or names: regex PATTERNS in the same file
Anything without a translation stays English, so a missing entry never breaks a response.
Set I18N_REPORT_MISSING=/path/file to append untranslated sentences there (used to keep the dictionary complete).
"""
from __future__ import annotations

import os
import re
from contextvars import ContextVar

SUPPORTED = ("en", "mn")
_lang: ContextVar[str] = ContextVar("faceguard_lang", default="en")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"(])")


def parse_accept_language(header: str | None) -> str:
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()
        if code.startswith("mn"):
            return "mn"
        if code.startswith("en"):
            return "en"
    return "en"


def set_lang(lang: str):
    return _lang.set(lang if lang in SUPPORTED else "en")


def get_lang() -> str:
    return _lang.get()


def _report(sentence: str) -> None:
    path = os.environ.get("I18N_REPORT_MISSING")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(sentence.replace("\n", " ") + "\n")


def _one(sentence: str) -> str:
    from app.locales.mn import PATTERNS, SENTENCES
    if sentence in SENTENCES:
        return SENTENCES[sentence]
    for rx, tpl in PATTERNS:
        m = rx.fullmatch(sentence)
        if m:
            if callable(tpl):  # needs to translate parts of the match itself (e.g. a nested sentence or a list)
                return tpl(m, _translate_inner)
            return tpl.format(*(tr_fragment(g) if g is not None else "" for g in m.groups()))
    _report(sentence)
    return sentence


def _translate_inner(text: str) -> str:
    return " ".join(_one(x) for x in _SPLIT.split(text.strip()) if x)


def tr_fragment(text: str) -> str:
    """Translates a captured fragment only if it is a known sentence/word (e.g. a status name); never reports."""
    from app.locales.mn import SENTENCES
    return SENTENCES.get(text, text)


def tr(text: str | None, lang: str | None = None) -> str | None:
    """Translates a message into the request language, one sentence at a time."""
    if text is None or (lang or get_lang()) != "mn" and not os.environ.get("I18N_REPORT_MISSING"):
        return text
    parts = [_one(s) for s in _SPLIT.split(text.strip()) if s]
    out = " ".join(parts)
    return out if (lang or get_lang()) == "mn" else text


def tr_list(items: list[str] | None) -> list[str] | None:
    return None if items is None else [tr(x) for x in items]
