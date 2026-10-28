import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from src.domain.entities.robot_command import CommandType, RobotPose, Telemetry
from src.domain.entities.user import UserRole
from src.frameworks.db.repositories.command_log_repo import SqlCommandLogRepository
from src.frameworks.db.session import get_db
from src.frameworks.ros.rosbridge_client import RosBridgeClient, get_rosbridge_client
from src.frameworks.security.rbac import current_user, require_role, ws_auth
from src.use_cases.robot.send_command import SendCommandInput, SendCommandUseCase

router = APIRouter()


class CommandRequest(BaseModel):
    command: CommandType
    payload: dict = {}


class CommandResponse(BaseModel):
    id: str
    command_type: str
    acknowledged: bool


class PoseResponse(BaseModel):
    x: float
    y: float
    theta: float
    frame_id: str
    source: str
    timestamp: float
    age_seconds: float
    stale: bool
    robot_connected: bool


def _pose_to_response(pose: RobotPose, connected: bool) -> PoseResponse:
    age = max(0.0, time.time() - pose.timestamp)
    return PoseResponse(
        x=pose.x, y=pose.y, theta=pose.theta, frame_id=pose.frame_id, source=pose.source,
        timestamp=pose.timestamp, age_seconds=round(age, 3),
        stale=age > settings.pose_stale_seconds, robot_connected=connected,
    )


@router.get("/pose", response_model=PoseResponse)
async def get_pose(
    _payload: dict = Depends(current_user),
    ros: RosBridgeClient = Depends(get_rosbridge_client),
):
    """Текущее положение робота.

    frame_id="map" — координаты на карте (AMCL, совпадают с координатами редактора и QR-меток);
    frame_id="odom" — только одометрия, если локализация не запущена.
    """
    pose = ros.current_pose()
    if pose is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Положение робота пока неизвестно")
    return _pose_to_response(pose, ros.is_connected)


@router.post("/command", response_model=CommandResponse)
async def send_command(
    body: CommandRequest,
    payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
    ros: RosBridgeClient = Depends(get_rosbridge_client),
):
    try:
        use_case = SendCommandUseCase(ros, SqlCommandLogRepository(db))
        result = await use_case.execute(
            SendCommandInput(
                user_id=payload["sub"],
                command_type=body.command,
                payload=body.payload,
            )
        )
        return CommandResponse(id=str(result.id), command_type=result.command_type.value, acknowledged=result.acknowledged)
    except ConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket, ros: RosBridgeClient = Depends(get_rosbridge_client)):
    try:
        await ws_auth(websocket)
    except ValueError:
        return

    await websocket.accept()
    queue: asyncio.Queue[Telemetry] = asyncio.Queue(maxsize=10)

    def on_telemetry(t: Telemetry) -> None:
        try:
            queue.put_nowait(t)
        except asyncio.QueueFull:
            pass

    ros.subscribe_telemetry(on_telemetry)
    try:
        while True:
            try:
                telemetry = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_text(
                    json.dumps({
                        "x": telemetry.x,
                        "y": telemetry.y,
                        "theta": telemetry.theta,
                        "battery_percent": telemetry.battery_percent,
                        "task_status": telemetry.task_status,
                        "timestamp": telemetry.timestamp,
                        "robot_connected": ros.is_connected,
                        "pose": _pose_payload(ros),
                    })
                )
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"ping": 1, "robot_connected": ros.is_connected}))
    except WebSocketDisconnect:
        pass
    finally:
        ros.unsubscribe_telemetry(on_telemetry)


def _pose_payload(ros: RosBridgeClient) -> dict | None:
    pose = ros.current_pose()
    return _pose_to_response(pose, ros.is_connected).model_dump() if pose else None
