from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.entities.user import UserRole
from src.frameworks.security.jwt_handler import decode_token

_bearer = HTTPBearer()


def _extract_payload(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется access-токен")
    return payload


def current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    try:
        return _extract_payload(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_role(*roles: UserRole):
    def _dep(payload: dict = Depends(current_user)) -> dict:
        if payload.get("role") not in [r.value for r in roles]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return payload

    return _dep


async def ws_auth(websocket: WebSocket) -> dict:
    token = websocket.query_params.get("token") or websocket.headers.get("authorization", "").removeprefix("Bearer ")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise ValueError("Токен отсутствует")
    try:
        return _extract_payload(token)
    except (ValueError, Exception) as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise ValueError(str(exc)) from exc
