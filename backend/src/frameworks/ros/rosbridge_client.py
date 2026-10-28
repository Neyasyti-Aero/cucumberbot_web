import asyncio
import itertools
import json
import logging
import math
import time
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings
from src.domain.entities.robot_command import RobotPose, Telemetry

logger = logging.getLogger(__name__)

TelemetryCallback = Callable[[Telemetry], None]

SIM_PHASE_SECONDS = 30.0
SIM_STATUSES = ["patrol", "collect", "return_to_base", "idle"]
SIM_RADIUS = 2.5
SIM_ANGULAR_SPEED = 0.15
SIM_BATTERY_PERIOD = 180.0


def quaternion_to_yaw(q: dict) -> float:
    """Yaw (рад) из geometry_msgs/Quaternion."""
    x, y, z, w = (q.get(k, 0.0) for k in ("x", "y", "z", "w"))
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


class RosBridgeClient:
    def __init__(self) -> None:
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscribers: list[TelemetryCallback] = []
        self._latest: Telemetry = Telemetry(x=0, y=0, theta=0, battery_percent=0, task_status="idle", timestamp=0)
        self._running = False
        self._connected = False
        self._was_connected = False
        self._task: asyncio.Task | None = None
        self._sim_task: asyncio.Task | None = None
        self._sim_start = time.monotonic()
        self._odom_pose: RobotPose | None = None
        self._map_pose: RobotPose | None = None
        self._ids = itertools.count(1)
        self._pending: dict[str, asyncio.Future] = {}

    @property
    def latest_telemetry(self) -> Telemetry:
        return self._latest

    @property
    def is_connected(self) -> bool:
        return self._connected

    def current_pose(self) -> RobotPose | None:
        """Лучшая известная поза: в кадре map (AMCL), если свежая, иначе одометрия."""
        now = time.time()
        for pose in (self._map_pose, self._odom_pose):
            if pose and now - pose.timestamp <= settings.pose_stale_seconds:
                return pose
        return self._map_pose or self._odom_pose

    def subscribe_telemetry(self, callback: TelemetryCallback) -> None:
        self._subscribers.append(callback)

    def unsubscribe_telemetry(self, callback: TelemetryCallback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def connect(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        if settings.ros_simulation:
            self._sim_task = asyncio.create_task(self._sim_loop())

    async def disconnect(self) -> None:
        self._running = False
        for task in (self._task, self._sim_task):
            if task:
                task.cancel()
        if self._ws:
            await self._ws.close()

    async def advertise(self, topic: str, msg_type: str, latch: bool = False) -> None:
        if not self._ws:
            raise ConnectionError("Нет соединения с rosbridge")
        frame = {"op": "advertise", "topic": topic, "type": msg_type, "latch": latch}
        await self._ws.send(json.dumps(frame))

    async def publish(self, topic: str, message: dict) -> None:
        if not self._ws:
            raise ConnectionError("Нет соединения с rosbridge")
        frame = {"op": "publish", "topic": topic, "msg": message}
        await self._ws.send(json.dumps(frame))

    async def call_service(self, service: str, args: dict) -> dict:
        if not self._ws:
            raise ConnectionError("Нет соединения с rosbridge")
        # Ответ разбирает _receive_loop по id — читать ws.recv() здесь нельзя, это гонка с циклом приёма
        call_id = f"call_service:{next(self._ids)}"
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[call_id] = future
        try:
            frame = {"op": "call_service", "id": call_id, "service": service, "args": args}
            await self._ws.send(json.dumps(frame))
            response = await asyncio.wait_for(future, timeout=5.0)
        finally:
            self._pending.pop(call_id, None)
        if response.get("result") is False:
            raise RuntimeError(f"Сервис {service} вернул ошибку: {response.get('values')}")
        return response.get("values", {})

    async def _run_loop(self) -> None:
        while self._running:
            try:
                async with websockets.connect(settings.rosbridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    self._was_connected = True
                    logger.info("Подключено к rosbridge: %s", settings.rosbridge_url)
                    await self._subscribe_topics(ws)
                    await self._receive_loop(ws)
            except (ConnectionClosed, OSError) as exc:
                self._ws = None
                self._connected = False
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(ConnectionError("Соединение с rosbridge потеряно"))
                if self._was_connected:
                    logger.warning(
                        "Rosbridge отключён: %s. Переподключение через %ss", exc, settings.rosbridge_reconnect_interval
                    )
                    self._was_connected = False
                else:
                    logger.debug(
                        "Rosbridge недоступен: %s. Переподключение через %ss", exc, settings.rosbridge_reconnect_interval
                    )
                await asyncio.sleep(settings.rosbridge_reconnect_interval)

    async def _subscribe_topics(self, ws) -> None:
        topics = [
            (settings.ros_odom_topic, "nav_msgs/msg/Odometry"),
            (settings.ros_pose_topic, "geometry_msgs/msg/PoseWithCovarianceStamped"),
            ("/battery_state", "sensor_msgs/msg/BatteryState"),
            ("/task_status", "std_msgs/msg/String"),
        ]
        for topic, msg_type in topics:
            await ws.send(json.dumps({"op": "subscribe", "topic": topic, "type": msg_type}))

    async def _receive_loop(self, ws) -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if msg.get("op") == "publish":
                    self._handle_topic(msg["topic"], msg["msg"])
                elif msg.get("op") == "service_response":
                    future = self._pending.get(msg.get("id", ""))
                    if future and not future.done():
                        future.set_result(msg)
            except Exception as exc:
                logger.debug("Ошибка парсинга rosbridge сообщения: %s", exc)

    def _emit(self, telemetry: Telemetry) -> None:
        self._latest = telemetry
        for cb in self._subscribers:
            try:
                cb(self._latest)
            except Exception as exc:
                logger.debug("Telemetry callback error: %s", exc)

    def _handle_topic(self, topic: str, msg: dict) -> None:
        if topic == settings.ros_pose_topic:
            self._map_pose = self._parse_pose(msg, default_frame="map", source="amcl")
            return
        if topic == settings.ros_odom_topic:
            odom = self._parse_pose(msg, default_frame="odom", source="odom")
            self._odom_pose = odom
            telemetry = Telemetry(
                x=odom.x,
                y=odom.y,
                theta=odom.theta,
                battery_percent=self._latest.battery_percent,
                task_status=self._latest.task_status,
                timestamp=time.time(),
            )
        elif topic == "/battery_state":
            telemetry = Telemetry(
                x=self._latest.x,
                y=self._latest.y,
                theta=self._latest.theta,
                battery_percent=msg.get("percentage", self._latest.battery_percent) * 100,
                task_status=self._latest.task_status,
                timestamp=time.time(),
            )
        elif topic == "/task_status":
            telemetry = Telemetry(
                x=self._latest.x,
                y=self._latest.y,
                theta=self._latest.theta,
                battery_percent=self._latest.battery_percent,
                task_status=msg.get("data", self._latest.task_status),
                timestamp=time.time(),
            )
        else:
            return

        self._emit(telemetry)

    @staticmethod
    def _parse_pose(msg: dict, default_frame: str, source: str) -> RobotPose:
        # Odometry и PoseWithCovarianceStamped: pose.pose.{position,orientation}
        pose = msg.get("pose", {}).get("pose", {})
        pos = pose.get("position", {})
        return RobotPose(
            x=pos.get("x", 0.0),
            y=pos.get("y", 0.0),
            theta=quaternion_to_yaw(pose.get("orientation", {})),
            frame_id=msg.get("header", {}).get("frame_id") or default_frame,
            source=source,
            timestamp=time.time(),
        )

    async def _sim_loop(self) -> None:
        """Имитирует телеметрию робота, когда реальное подключение к rosbridge отсутствует."""
        while self._running:
            await asyncio.sleep(1.0)
            if self._connected:
                continue
            telemetry = self._simulate()
            self._map_pose = RobotPose(
                x=telemetry.x, y=telemetry.y, theta=telemetry.theta,
                frame_id="map", source="simulation", timestamp=telemetry.timestamp,
            )
            self._emit(telemetry)

    def _simulate(self) -> Telemetry:
        t = time.monotonic() - self._sim_start
        phase_idx = int((t // SIM_PHASE_SECONDS) % len(SIM_STATUSES))
        status = SIM_STATUSES[phase_idx]
        phase_progress = (t % SIM_PHASE_SECONDS) / SIM_PHASE_SECONDS

        angle = t * SIM_ANGULAR_SPEED
        cx, cy = SIM_RADIUS * math.cos(angle), SIM_RADIUS * math.sin(angle)

        if status == "return_to_base":
            x, y = cx * (1 - phase_progress), cy * (1 - phase_progress)
        elif status == "idle":
            x, y = 0.0, 0.0
        else:
            x, y = cx, cy

        theta = (angle + math.pi / 2) % (2 * math.pi)
        battery = 30.0 + 35.0 * (1 + math.cos(2 * math.pi * t / SIM_BATTERY_PERIOD))

        return Telemetry(x=x, y=y, theta=theta, battery_percent=battery, task_status=status, timestamp=time.time())


_client: RosBridgeClient | None = None


def get_rosbridge_client() -> RosBridgeClient:
    global _client
    if _client is None:
        _client = RosBridgeClient()
    return _client
