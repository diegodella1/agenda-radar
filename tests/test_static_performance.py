import pytest

from agenda_radar.app import ASSET_VERSIONS


@pytest.mark.parametrize('name', ['app.js', 'jobs.js', 'app.css', 'fonts/fira-sans-regular.woff2'])
def test_versioned_assets_cache_and_revalidate(client, name):
    url = f'/static/{name}?v={ASSET_VERSIONS[name]}'
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'public, max-age=31536000, immutable'
    conditional = client.get(url, headers={'If-None-Match': response.headers['etag']})
    assert conditional.status_code == 304
    for suffix in ['', '?v=old']:
        assert client.get(f'/static/{name}{suffix}').headers['cache-control'] == 'public, max-age=0, must-revalidate'


def test_static_compression_and_private_responses(client):
    response = client.get('/static/app.css', headers={'Accept-Encoding': 'gzip'})
    assert response.headers['content-encoding'] == 'gzip'
    assert 'Accept-Encoding' in response.headers['vary']
    for path in ['/', '/api/v1/auth/me', '/static/missing.js?v=missing']:
        assert client.get(path).headers['cache-control'] == 'no-store'


def test_demo_assets_without_creating_visit(app):
    from fastapi.testclient import TestClient

    from agenda_radar.app import create_app

    settings = app.state.settings.model_copy(update={'demo_enabled': True})
    demo_app = create_app(settings)
    with TestClient(demo_app) as client:
        login = client.get('/demo/login')
        assert login.status_code == 200
        assert f'/demo/static/app.js?v={ASSET_VERSIONS["app.js"]}' in login.text
        response = client.get(f'/demo/static/app.js?v={ASSET_VERSIONS["app.js"]}')
        assert response.status_code == 200
        assert 'immutable' in response.headers['cache-control']
        assert not response.cookies
    demo_app.state.db.engine.dispose()
