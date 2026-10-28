import math
import time

from src.frameworks.ros.rosbridge_client import RosBridgeClient, quaternion_to_yaw


def _q(yaw: float) -> dict:
    return {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2), "w": math.cos(yaw / 2)}


def _msg(x: float, y: float, yaw: float, frame: str | None = None) -> dict:
    msg = {"pose": {"pose": {"position": {"x": x, "y": y}, "orientation": _q(yaw)}}}
    if frame:
        msg["header"] = {"frame_id": frame}
    return msg


def test_quaternion_to_yaw():
    for yaw in (0.0, 0.5, math.pi / 2, -2.0, 3.0):
        assert math.isclose(quaternion_to_yaw(_q(yaw)), yaw, abs_tol=1e-9)


def test_amcl_pose_preferred_over_odom():
    client = RosBridgeClient()
    client._handle_topic("/odom", _msg(1, 2, 0.3, "odom"))
    pose = client.current_pose()
    assert pose.frame_id == "odom" and math.isclose(pose.theta, 0.3)
    assert math.isclose(client.latest_telemetry.theta, 0.3)

    client._handle_topic("/amcl_pose", _msg(5, 6, 1.0, "map"))
    pose = client.current_pose()
    assert (pose.x, pose.y, pose.frame_id, pose.source) == (5, 6, "map", "amcl")


def test_stale_amcl_falls_back_to_odom():
    client = RosBridgeClient()
    client._handle_topic("/amcl_pose", _msg(5, 0, 0))
    client._map_pose.timestamp = time.time() - 60
    client._handle_topic("/odom", _msg(1, 0, 0))
    assert client.current_pose().source == "odom"
