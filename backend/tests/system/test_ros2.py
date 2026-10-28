"""Интеграция с ROS 2 через настоящий rosbridge_server (Humble).

Запуск:  SYSTEM_BASE_URL=... SYSTEM_ROSBRIDGE_URL=ws://rosbridge:9090 pytest tests/system
"""

import json
import math
import os
import time

import httpx
import pytest
from websockets.sync.client import connect

from tests.system.conftest import BASE_URL

ROSBRIDGE_URL = os.environ.get("SYSTEM_ROSBRIDGE_URL", "")

pytestmark = pytest.mark.skipif(not (BASE_URL and ROSBRIDGE_URL), reason="SYSTEM_ROSBRIDGE_URL не задан")


def _wait_robot_connected(c: httpx.Client) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        if c.get("/health").json().get("robot_connected"):
            return
        time.sleep(1)
    pytest.fail("backend не подключился к rosbridge")


def test_map_published_as_occupancy_grid(client, map_id):
    _wait_robot_connected(client)
    expected = client.get(f"/maps/{map_id}/nav2/validate").json()

    with connect(ROSBRIDGE_URL, open_timeout=10, max_size=None) as ws:
        ws.send(json.dumps({"op": "subscribe", "topic": "/map", "type": "nav_msgs/msg/OccupancyGrid"}))
        time.sleep(1)
        r = client.post(f"/maps/{map_id}/publish")
        assert r.status_code == 200, r.text

        deadline = time.time() + 20
        msg = None
        while time.time() < deadline:
            frame = json.loads(ws.recv(timeout=deadline - time.time()))
            if frame.get("op") == "publish" and frame.get("topic") == "/map":
                msg = frame["msg"]
                break
        assert msg, "сообщение /map не получено"

    info = msg["info"]
    assert msg["header"]["frame_id"] == "map"
    assert (info["width"], info["height"]) == (expected["width"], expected["height"])
    assert math.isclose(info["resolution"], expected["resolution"], rel_tol=1e-6)
    assert math.isclose(info["origin"]["position"]["x"], expected["origin"][0], abs_tol=1e-6)
    assert len(msg["data"]) == info["width"] * info["height"]
    assert set(msg["data"]) <= {-1, 0, 100}
    assert msg["data"].count(0) == expected["cells"]["free"]


def test_amcl_pose_reaches_pose_api(client):
    _wait_robot_connected(client)
    yaw = 1.2
    pose_msg = {
        "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
        "pose": {
            "pose": {
                "position": {"x": 3.25, "y": 1.5, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)},
            },
            "covariance": [0.0] * 36,
        },
    }
    with connect(ROSBRIDGE_URL, open_timeout=10) as ws:
        ws.send(json.dumps({
            "op": "advertise", "topic": "/amcl_pose", "type": "geometry_msgs/msg/PoseWithCovarianceStamped",
        }))
        deadline = time.time() + 20
        while time.time() < deadline:
            ws.send(json.dumps({"op": "publish", "topic": "/amcl_pose", "msg": pose_msg}))
            r = client.get("/robot/pose")
            if r.status_code == 200 and r.json()["source"] == "amcl":
                break
            time.sleep(0.5)

    pose = r.json()
    assert pose["source"] == "amcl" and pose["frame_id"] == "map"
    assert (pose["x"], pose["y"]) == (3.25, 1.5)
    assert math.isclose(pose["theta"], yaw, abs_tol=1e-6)
    assert pose["robot_connected"] is True
