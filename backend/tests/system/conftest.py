"""Общие фикстуры системных тестов: адрес стека, логин администратора, тестовая карта."""

import os

import httpx
import pytest

BASE_URL = os.environ.get("SYSTEM_BASE_URL", "").rstrip("/")
ADMIN_EMAIL = os.environ.get("SYSTEM_ADMIN_EMAIL", "admin@cucumberbot.io")
ADMIN_PASSWORD = os.environ.get("SYSTEM_ADMIN_PASSWORD", "Admin1234!")

LAYOUT = {
    "type": "FeatureCollection",
    "properties": {"mapMode": "relative"},
    "features": [
        {
            "type": "Feature",
            "properties": {"featureType": "zone", "isRoom": True},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 6], [0, 6], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"featureType": "zone"},
            "geometry": {"type": "Polygon", "coordinates": [[[2, 1], [3, 1], [3, 5], [2, 5], [2, 1]]]},
        },
        {
            "type": "Feature",
            "properties": {"featureType": "qr", "label": "Вход"},
            "geometry": {"type": "Point", "coordinates": [1, 0.5]},
        },
    ],
}


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=f"{BASE_URL}/api/v1", timeout=30) as c:
        r = c.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        yield c


@pytest.fixture(scope="module")
def map_id(client):
    r = client.post("/maps/templates", json={"name": "system-test", "map_type": "relative", "geojson": LAYOUT})
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    yield mid
    client.delete(f"/maps/{mid}")
