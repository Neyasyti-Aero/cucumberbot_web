from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.frameworks.db.repositories.user_repo import SqlUserRepository
from src.frameworks.db.session import get_db
from src.frameworks.security.jwt_handler import create_token_pair, decode_token
from src.use_cases.auth.login import LoginInput, LoginUseCase

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    repo = SqlUserRepository(db)
    use_case = LoginUseCase(repo)
    try:
        result = await use_case.execute(LoginInput(email=body.email, password=body.password))
        return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Требуется refresh-токен")
        pair = create_token_pair(payload["sub"], payload["role"])
        return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
