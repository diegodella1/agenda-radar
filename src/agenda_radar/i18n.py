"""Request-scoped UI translation. Editorial content is never machine-translated."""

import json
import re
from contextvars import ContextVar
from pathlib import Path

language = ContextVar("ui_language", default="en")
TRANSLATIONS = json.loads((Path(__file__).parent / "static" / "translations.json").read_text())


def translate(message):
    if not isinstance(message, str) or language.get() == "es":
        return message
    if message in TRANSLATIONS:
        return TRANSLATIONS[message]
    match = re.fullmatch(r"Afinidad con tu criterio: (\d+)%\. (.+)", message)
    if match:
        return f"Affinity with your priorities: {match[1]}%. {translate(match[2])}"
    return message


def request_language(request, default="en"):
    selected = request.query_params.get("lang")
    if selected in {"en", "es"}:
        return selected
    saved = request.cookies.get("radar_lang")
    return saved if saved in {"en", "es"} else default
