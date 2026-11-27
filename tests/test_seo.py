import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from agenda_radar.seo import PUBLIC_PATHS


def test_discovery_and_language_urls(app):
    with TestClient(app) as visitor:
        robots = visitor.get("/robots.txt")
        assert robots.status_code == 200
        assert "Sitemap:" in robots.text and "Disallow: /\n" not in robots.text
        response = visitor.get("/sitemap.xml")
        assert response.status_code == 200
        urls = [node.text for node in ET.fromstring(response.text).iter() if node.tag.endswith("}loc")]
        assert len(urls) == 10 and len(set(urls)) == 10
        assert not any("demo" in url or "login" in url for url in urls)
        titles = set()
        visitor.cookies.set("radar_lang", "es")
        for path in PUBLIC_PATHS:
            for lang in ("en", "es"):
                response = visitor.get(f"{path}?lang={lang}")
                assert response.status_code == 200
                assert "noindex" not in response.headers.get("x-robots-tag", "")
                soup = BeautifulSoup(response.text, "html.parser")
                assert soup.html["lang"] == lang
                assert len(soup.select("h1")) == 1
                canonical = soup.select_one('link[rel="canonical"]')["href"]
                assert canonical.endswith(f"{path}?lang={lang}")
                assert canonical in urls
                alternatives = {link["hreflang"]: link["href"] for link in soup.select("link[hreflang]")}
                assert set(alternatives) == {"en", "es", "x-default"}
                assert alternatives[lang] == canonical
                assert alternatives["x-default"] == alternatives["en"]
                assert soup.select_one('[itemtype="https://schema.org/SoftwareApplication"]')
                assert soup.select_one('[itemprop="description"]').get_text(strip=True)
                assert "demo / demo" not in response.text
                titles.add(soup.title.get_text())
        assert len(titles) == 10


def test_account_and_unknown_pages_are_not_indexable(client):
    for path in ("/", "/login", "/admin", "/not-a-real-page", "/api/v1/events"):
        response = client.get(path)
        assert "noindex" in response.headers["x-robots-tag"]
    assert "noindex" not in client.get("/home").headers.get("x-robots-tag", "")
