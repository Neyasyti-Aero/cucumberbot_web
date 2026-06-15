import asyncio
import shlex

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from src.frameworks.security.rbac import ws_auth

router = APIRouter()

ALLOWED = set(settings.terminal_allowed_commands)


def _is_allowed(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return bool(parts) and parts[0] in ALLOWED


@router.websocket("/ws")
async def terminal_ws(websocket: WebSocket):
    try:
        await ws_auth(websocket)
    except ValueError:
        return

    await websocket.accept()
    await websocket.send_text("\x1b[32mCucumberBot Terminal — введите команду\x1b[0m\r\n")

    try:
        while True:
            raw = await websocket.receive_text()
            command = raw.strip()

            if not command:
                continue

            if not _is_allowed(command):
                await websocket.send_text(f"\x1b[31mКоманда запрещена: {command}\x1b[0m\r\n")
                continue

            await _run_command(websocket, command)
    except WebSocketDisconnect:
        pass


async def _run_command(ws: WebSocket, command: str) -> None:
    try:
        args = shlex.split(command)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=settings.terminal_sandbox_dir,
        )

        async def _stream():
            assert proc.stdout is not None
            async for line in proc.stdout:
                await ws.send_text(line.decode(errors="replace"))

        await asyncio.wait_for(
            asyncio.gather(_stream(), proc.wait()),
            timeout=settings.terminal_timeout_seconds,
        )
        await ws.send_text(f"\x1b[90m[код выхода: {proc.returncode}]\x1b[0m\r\n")

    except asyncio.TimeoutError:
        await ws.send_text("\x1b[31m[Превышен лимит времени]\x1b[0m\r\n")
    except Exception as exc:
        await ws.send_text(f"\x1b[31m[Ошибка]: {exc}\x1b[0m\r\n")
