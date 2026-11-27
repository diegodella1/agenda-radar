"""Curated public Argentine publishers. Profiles are evidence, not extra publishers."""

VERSION = "argentina-real-v2"
VERIFIED_AT = "2026-10-16"
TOPIC_KEYWORDS = {
    "economía": ["inflación", "dólar", "economía", "presupuesto", "salarios", "comercio"],
    "política": ["congreso", "gobierno", "elecciones", "senado", "Milei", "legislatura"],
    "sociedad": ["municipio", "vecinos", "barrio", "policía", "justicia"],
    "deportes": ["fútbol", "deportes", "River", "Boca", "Messi", "torneo", "selección"],
    "salud": ["salud", "hospital", "médico", "vacunas", "cáncer"],
    "educación": ["educación", "universidad", "escuelas", "docentes", "becas"],
    "ambiente": ["ambiente", "inundaciones", "lluvias", "clima", "incendios", "El Niño"],
    "transporte": ["transporte", "trenes", "colectivos", "aeropuerto", "vuelos"],
    "cultura": ["cultura", "música", "cine", "festival", "teatro"],
}
YOUTUBE_CHANNELS = {
    "www.infobae.com": "UCvsU0EGXN7Su7MfNqcTGNHg",
    "www.pagina12.com.ar": "UCJNDedOnljCssaiRZqg8-Dg",
    "www.lavoz.com.ar": "UCluV_ArZV6NOdQIWiXTJx3g",
    "www.lagaceta.com.ar": "UCowbI8idnvQTl2sFxkOvnKw",
    "www.ellitoral.com": "UCRtZO3mPqvCMYfmJogXyW7g",
    "www.losandes.com.ar": "UCA_4ak2pN7yNzrvBzQcRv4Q",
    "www.rionegro.com.ar": "UCGcERTpPSOt9PuNf0JVe50w",
}

# name, domain, region, editorial group, feed, X, Instagram, Facebook, YouTube
MEDIA = [
    ("LA NACION", "www.lanacion.com.ar", "Nacional", "LA NACION",
     "/arc/outboundfeeds/rss/?outputType=xml", "LANACION", "lanacioncom", "lanacion", ""),
    ("Infobae", "www.infobae.com", "Nacional", "Infobae",
     "/arc/outboundfeeds/rss/tags_slug/argentina/", "Infobae", "Infobae", "", "c/infobae"),
    ("Página/12", "www.pagina12.com.ar", "Nacional", "Grupo Octubre",
     "/arc/outboundfeeds/rss/portada", "pagina12", "pagina12", "Pagina12ok",
     "channel/UCJNDedOnljCssaiRZqg8-Dg"),
    ("La Voz", "www.lavoz.com.ar", "Centro", "Grupo Clarín",
     "/", "lavozcomar", "lavozcomar", "", "user/LVIcomar"),
    ("La Gaceta", "www.lagaceta.com.ar", "NOA", "La Gaceta",
     "/rss", "lagacetatucuman", "lagacetatucuman", "lagaceta", "user/lagacetatucuman"),
    ("El Litoral", "www.ellitoral.com", "Litoral", "El Litoral",
     "/rss", "ellitoral", "ellitoral", "ellitoralcom", "ellitoralcom"),
    ("Los Andes", "www.losandes.com.ar", "Cuyo", "Grupo Clarín",
     "/", "LosAndesDiario", "losandesdiario",
     "LosAndesDiario", "user/LosAndesDiario"),
    ("Río Negro", "www.rionegro.com.ar", "Patagonia", "Editorial Río Negro",
     "/feed/", "rionegrocomar", "rionegrocomar", "diariorionegro", "user/diariorionegro"),
]


def catalog():
    rows = []
    for name, domain, region, group, feed, x, instagram, facebook, youtube in MEDIA:
        website = f"https://{domain}/"
        profiles = {key: f"https://{host}/{handle}" for key, host, handle in (
            ("x", "x.com", x), ("instagram", "www.instagram.com", instagram),
            ("facebook", "www.facebook.com", facebook),
            ("youtube", "www.youtube.com", youtube),
        ) if handle}
        if domain in ("www.lagaceta.com.ar", "www.losandes.com.ar", "www.rionegro.com.ar"):
            profiles["tiktok"] = f"https://www.tiktok.com/@{instagram}"
        options = {
            "catalog_id": domain, "catalog_version": VERSION, "website": website,
            "region": region, "topics": ["actualidad", "política", "economía", "sociedad", "deportes"],
            "profiles": profiles, "verified_at": VERIFIED_AT,
            "profile_evidence": website if profiles else None,
            "profile_status": "verified" if profiles else "pending",
            "group_evidence": (
                "https://www.grupoclarin.com/sites/default/files/Memoria-Anual-Integral-GC-2022.pdf"
                if group == "Grupo Clarín" else website
            ),
        }
        base = dict(name=name, kind="rss", channel="web", scope="reference",
                    group_name=group, country="AR", poll_interval=3600,
                    legal_basis="Feed público: títulos, extractos breves y enlace al original",
                    options=options, url=f"https://{domain}{feed}")
        rows.append(base)
        if domain in ("www.ellitoral.com", "www.lavoz.com.ar", "www.losandes.com.ar"):
            base.update(kind="web", url=website)
            base["legal_basis"] = "Portada pública conforme robots: títulos y enlaces al original"
        if domain == "www.ellitoral.com":
            options["article_selector"] = "a[href]:has(h1), a[href]:has(h2)"
        if x:
            rows.append({**base, "name": name + " · X", "kind": "x", "channel": "x",
                         "scope": "public", "poll_interval": 3600, "url": profiles["x"],
                         "options": {**options, "catalog_id": domain + ":x", "username": x}})
        if youtube:
            identifier = YOUTUBE_CHANNELS[domain]
            rows.append({**base, "name": name + " · YouTube", "kind": "rss", "channel": "video",
                         "scope": "public", "poll_interval": 3600,
                         "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={identifier}",
                         "enabled": True, "status": "pending", "error_code": None,
                         "options": {**options, "catalog_id": domain + ":youtube",
                                     "channel_id": identifier,
                                     "channel_evidence": f"https://www.youtube.com/channel/{identifier}"}})
    rows.append(dict(name="Google Trends · Argentina", url="https://trends.google.com/trending/rss?geo=AR",
                     kind="google_trends", channel="search", scope="public", group_name="Google",
                     country="AR", poll_interval=3600,
                     legal_basis="Exportación pública RSS de Google Trends Argentina",
                     options={"catalog_id": "google-trends-ar", "region": "Nacional",
                              "website": "https://trends.google.com/trending?geo=AR"}))
    return rows
