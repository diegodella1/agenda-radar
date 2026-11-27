from fastapi.testclient import TestClient


def test_public_pages_do_not_expose_editorial_data(app):
    with TestClient(app) as visitor:
        for path in ("/", "/home", "/about", "/funcionalidades", "/casos-de-uso", "/roadmap"):
            response = visitor.get(path)
            assert response.status_code == 200
            assert 'href="/login"' in response.text
            assert "admin@example.test" not in response.text
            assert 'name="description"' in response.text
            assert "/static/public.css?v=" in response.text
        assert visitor.get("/api/v1/events").status_code == 401
        assert visitor.get("/compare", follow_redirects=False).status_code == 303


def test_signed_in_root_keeps_editorial_dashboard(client):
    assert "Radar editorial" in client.get("/").text
    assert "Dejá de revisar 40 pestañas antes de la reunión de pauta." in client.get("/home").text


def test_stylesheets_are_css_not_templates(app):
    with TestClient(app) as visitor:
        for path in ("/static/app.css", "/static/public.css"):
            response = visitor.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/css")
            assert "{%" not in response.text and "{{" not in response.text
            assert "<html" not in response.text and "<div" not in response.text
            assert "@font-face" in response.text
            assert "'Radar Sans','Radar Fallback',sans-serif" in response.text
            assert "format('woff2')" in response.text
            assert "--paper:#f3f6fb" in response.text
