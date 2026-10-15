from fastapi.testclient import TestClient


def test_public_pages_do_not_expose_editorial_data(app):
    with TestClient(app) as visitor:
        for path in ("/", "/home", "/about", "/funcionalidades", "/casos-de-uso", "/roadmap"):
            response = visitor.get(path)
            assert response.status_code == 200
            assert 'href="/login"' in response.text
            assert "admin@example.test" not in response.text
            assert 'name="description"' in response.text
        assert visitor.get("/api/v1/events").status_code == 401
        assert visitor.get("/compare", follow_redirects=False).status_code == 303


def test_signed_in_root_keeps_editorial_dashboard(client):
    assert "Radar editorial" in client.get("/").text
    assert "La noticia está." in client.get("/home").text
