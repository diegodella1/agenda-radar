"""Optional curated starter source packs; never preloaded automatically."""

from sqlalchemy import select

from .models import Source
from .schemas import SourceInput

PACKS: dict[str, dict] = {
    "ar_national": {
        "id": "ar_national",
        "name": "Argentina — Medios nacionales y tendencias",
        "name_en": "Argentina — National press & trends",
        "description": "Feeds RSS públicos de referencia nacional + Google Trends Argentina. Política inicial: interna.",
        "description_en": "Public national reference RSS feeds + Google Trends Argentina. Default policy: internal.",
        "sources": [
            {
                "name": "La Nación — Últimas noticias",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml",
                "scope": "reference",
                "group_name": "La Nación",
                "weight": 100,
                "poll_interval": 600,
                "country": "AR",
                "legal_basis": "Feed RSS público oficial para seguimiento de titulares y enlaces",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Clarín — Lo último",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.clarin.com/rss/lo-ultimo/",
                "scope": "reference",
                "group_name": "Grupo Clarín",
                "weight": 100,
                "poll_interval": 600,
                "country": "AR",
                "legal_basis": "Feed RSS público oficial para seguimiento de titulares y enlaces",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Infobae — Argentina",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.infobae.com/arc/outboundfeeds/rss/?outputType=xml",
                "scope": "reference",
                "group_name": "Infobae",
                "weight": 100,
                "poll_interval": 600,
                "country": "AR",
                "legal_basis": "Feed RSS público oficial para seguimiento de titulares y enlaces",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Página/12 — Portada",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.pagina12.com.ar/rss/portada",
                "scope": "reference",
                "group_name": "Grupo Octubre",
                "weight": 90,
                "poll_interval": 600,
                "country": "AR",
                "legal_basis": "Feed RSS público oficial para seguimiento de titulares y enlaces",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Ámbito Financiero — Economía",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.ambito.com/rss/pages/economia.xml",
                "scope": "reference",
                "group_name": "Grupo Indalo",
                "weight": 90,
                "poll_interval": 600,
                "country": "AR",
                "legal_basis": "Feed RSS público oficial para seguimiento de titulares y enlaces",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Google Trends Argentina",
                "kind": "google_trends",
                "channel": "search",
                "url": "https://trends.google.com/trending/rss?geo=AR",
                "scope": "public",
                "group_name": "Google Trends AR",
                "weight": 100,
                "poll_interval": 900,
                "country": "AR",
                "legal_basis": "Feed RSS público de Google Trends",
                "options": {"data_policy": "internal"},
            },
        ],
    },
    "intl_reference": {
        "id": "intl_reference",
        "name": "Referencia internacional (EN/ES)",
        "name_en": "International reference (EN/ES)",
        "description": "Medios internacionales de referencia en español e inglés + Google Trends US.",
        "description_en": "International reference RSS feeds in English & Spanish + Google Trends US.",
        "sources": [
            {
                "name": "BBC Mundo",
                "kind": "rss",
                "channel": "web",
                "url": "https://feeds.bbci.co.uk/mundo/rss.xml",
                "scope": "reference",
                "group_name": "BBC",
                "weight": 100,
                "poll_interval": 600,
                "country": "GB",
                "legal_basis": "Official public RSS feed",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "El País — Portada",
                "kind": "rss",
                "channel": "web",
                "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
                "scope": "reference",
                "group_name": "Prisa",
                "weight": 95,
                "poll_interval": 600,
                "country": "ES",
                "legal_basis": "Official public RSS feed",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "The Guardian — World",
                "kind": "rss",
                "channel": "web",
                "url": "https://www.theguardian.com/world/rss",
                "scope": "reference",
                "group_name": "Guardian Media Group",
                "weight": 95,
                "poll_interval": 600,
                "country": "GB",
                "legal_basis": "Official public RSS feed",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "NPR News",
                "kind": "rss",
                "channel": "web",
                "url": "https://feeds.npr.org/1001/rss.xml",
                "scope": "reference",
                "group_name": "NPR",
                "weight": 90,
                "poll_interval": 600,
                "country": "US",
                "legal_basis": "Official public RSS feed",
                "options": {"data_policy": "internal"},
            },
            {
                "name": "Google Trends US",
                "kind": "google_trends",
                "channel": "search",
                "url": "https://trends.google.com/trending/rss?geo=US",
                "scope": "public",
                "group_name": "Google Trends US",
                "weight": 100,
                "poll_interval": 900,
                "country": "US",
                "legal_basis": "Public Google Trends RSS feed",
                "options": {"data_policy": "internal"},
            },
        ],
    },
}


def list_packs() -> list[dict]:
    return [
        {
            "id": pack["id"],
            "name": pack["name"],
            "name_en": pack["name_en"],
            "description": pack["description"],
            "description_en": pack["description_en"],
            "count": len(pack["sources"]),
        }
        for pack in PACKS.values()
    ]


def apply_pack(session, pack_id: str) -> dict:
    pack = PACKS.get(pack_id)
    if not pack:
        raise ValueError("Pack de fuentes inexistente")
    created = 0
    skipped = 0
    for raw in pack["sources"]:
        payload = SourceInput.model_validate(raw)
        if session.scalar(select(Source.id).where(Source.url == payload.url)):
            skipped += 1
            continue
        session.add(Source(**payload.model_dump()))
        created += 1
    session.flush()
    return {"pack_id": pack_id, "created": created, "skipped": skipped}
