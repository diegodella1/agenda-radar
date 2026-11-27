"""Public discovery URLs. Demo and account content are intentionally not indexed."""

from xml.etree.ElementTree import Element, SubElement, tostring

PUBLIC_PATHS = ("/home", "/funcionalidades", "/casos-de-uso", "/about", "/roadmap")


def localized_url(base, path, language):
    return f"{base.rstrip('/')}{path}?lang={language}"


def sitemap(base):
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path in PUBLIC_PATHS:
        for language in ("en", "es"):
            entry = SubElement(root, "url")
            SubElement(entry, "loc").text = localized_url(base, path, language)
    return tostring(root, encoding="unicode", xml_declaration=True)
