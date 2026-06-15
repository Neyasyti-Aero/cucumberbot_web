import asyncio
import json
import logging
import math
import time
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings
from src.domain.entities.robot_command import Telemetry

logger = logging.getLogger(__name__)

TelemetryCallback = Callable[[Telemetry], None]

SIM_PHASE_SECONDS = 30.0
SIM_STATUSES = ["patrol", "collect", "return_to_base", "idle"]
SIM_RADIUS = 2.5
SIM_ANGULAR_SPEED = 0.15
SIM_BATTERY_PERIOD = 180.0


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

    @property
    def latest_telemetry(self) -> Telemetry:
        return self._latest

    @property
    def is_connected(self) -> bool:
        return self._connected

    def subscribe_telemetry(self, callback: TelemetryCallback) -> None:
        self._subscribers.append(callback)

    def unsubscribe_telemetry(self, callback: TelemetryCallback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def connect(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        self._sim_task = asyncio.create_task(self._sim_loop())

    async def disconnect(self) -> None:
        self._running = False
        for task in (self._task, self._sim_task):
            if task:
                task.cancel()
        if self._ws:
            await self._ws.close()

    async def publish(self, topic: str, message: dict) -> None:
        if not self._ws:
            raise ConnectionError("Нет соединения с rosbridge")
        frame = {"op": "publish", "topic": topic, "msg": message}
        await self._ws.send(json.dumps(frame))

    async def call_service(self, service: str, args: dict) -> dict:
        if not self._ws:
            raise ConnectionError("Нет соединения с rosbridge")
        frame = {"op": "call_service", "service": service, "args": args}
        await self._ws.send(json.dumps(frame))
        raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
        return json.loads(raw).get("values", {})

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
            ("/odom", "nav_msgs/Odometry"),
            ("/battery_state", "sensor_msgs/BatteryState"),
            ("/task_status", "std_msgs/String"),
        ]
        for topic, msg_type in topics:
            await ws.send(json.dumps({"op": "subscribe", "topic": topic, "type": msg_type}))

    async def _receive_loop(self, ws) -> None:
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if msg.get("op") == "publish":
                    self._handle_topic(msg["topic"], msg["msg"])
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
        if topic == "/odom":
            pose = msg.get("pose", {}).get("pose", {})
            pos = pose.get("position", {})
            ori = pose.get("orientation", {})
            telemetry = Telemetry(
                x=pos.get("x", self._latest.x),
                y=pos.get("y", self._latest.y),
                theta=ori.get("z", self._latest.theta),
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

    async def _sim_loop(self) -> None:
        """Имитирует телеметрию робота, когда реальное подключение к rosbridge отсутствует."""
        while self._running:
            await asyncio.sleep(1.0)
            if self._connected:
                continue
            self._emit(self._simulate())

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
