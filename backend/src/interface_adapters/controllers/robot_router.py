import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.robot_command import CommandType, Telemetry
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
                    })
                )
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"ping": 1, "robot_connected": ros.is_connected}))
    except WebSocketDisconnect:
        pass
    finally:
        ros.unsubscribe_telemetry(on_telemetry)
