"""Системные тесты против поднятого стека (nginx → backend → PostgreSQL/MinIO).

Запуск:  SYSTEM_BASE_URL=http://localhost:18080 pytest tests/system
Без SYSTEM_BASE_URL тесты пропускаются — в обычном `pytest` они не мешают.
"""

import io
import os
import zipfile

import httpx
import pytest
import yaml

from tests.system.conftest import BASE_URL

pytestmark = pytest.mark.skipif(not BASE_URL, reason="SYSTEM_BASE_URL не задан")


def test_frontend_and_health():
    assert httpx.get(f"{BASE_URL}/", timeout=10).status_code == 200
    assert httpx.get(f"{BASE_URL}/api/v1/health", timeout=10).json()["status"] == "ok"


def test_auth_required():
    assert httpx.get(f"{BASE_URL}/api/v1/robot/pose", timeout=10).status_code in (401, 403)


def test_nav2_validate(client, map_id):
    r = client.get(f"/maps/{map_id}/nav2/validate", params={"resolution": 0.05})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["valid"], report
    assert report["origin"] == [-0.5, -0.5, 0.0]
    assert report["cells"]["free"] > 0 and report["cells"]["occupied"] > 0


def test_nav2_export(client, map_id):
    r = client.get(f"/maps/{map_id}/nav2.zip")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        meta = yaml.safe_load(zf.read("map.yaml"))
        assert zf.read("map.pgm").startswith(b"P5")
    assert meta["image"] == "map.pgm" and meta["mode"] == "trinary"

    # CI загружает этот архив в настоящий nav2_map_server (docker/ros2/check_nav2_map.sh)
    if artifacts := os.environ.get("SYSTEM_ARTIFACTS_DIR"):
        with open(os.path.join(artifacts, "map.zip"), "wb") as f:
            f.write(r.content)


def test_qr_flow(client, map_id):
    r = client.post(f"/qr/maps/{map_id}/sync")
    assert r.status_code == 200, r.text
    created = r.json()["created"]
    assert len(created) == 1 and created[0]["label"] == "Вход"

    # повторная синхронизация не плодит дубликаты
    assert client.post(f"/qr/maps/{map_id}/sync").json()["created"] == []

    png = client.get(created[0]["image_url"].removeprefix("/api/v1"))
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")

    pdf = client.get(f"/qr/maps/{map_id}/sheet.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    landmarks = yaml.safe_load(client.get(f"/qr/maps/{map_id}/landmarks.yaml").text)
    assert landmarks["landmarks"][0]["id"] == created[0]["id"]


def test_robot_pose(client):
    r = client.get("/robot/pose")
    # 404 — допустимо, если робот не подключён и имитация выключена
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        assert r.json()["frame_id"] in ("map", "odom")
