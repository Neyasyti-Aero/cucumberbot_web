from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import UserRole
from src.frameworks.db.repositories.user_repo import SqlUserRepository
from src.frameworks.db.session import get_db
from src.frameworks.security.rbac import require_role
from src.use_cases.users.manage_users import CreateUserInput, ManageUsersUseCase, UpdateUserInput

router = APIRouter()


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.OPERATOR


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


@router.get("/", response_model=list[UserResponse])
async def list_users(
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = ManageUsersUseCase(SqlUserRepository(db))
    users = await uc.get_all()
    return [UserResponse(id=str(u.id), email=u.email, role=u.role.value, is_active=u.is_active) for u in users]


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        uc = ManageUsersUseCase(SqlUserRepository(db))
        user = await uc.create(CreateUserInput(email=body.email, password=body.password, role=body.role))
        return UserResponse(id=str(user.id), email=user.email, role=user.role.value, is_active=user.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        uc = ManageUsersUseCase(SqlUserRepository(db))
        user = await uc.update(UpdateUserInput(user_id=user_id, **body.model_dump(exclude_none=True)))
        return UserResponse(id=str(user.id), email=user.email, role=user.role.value, is_active=user.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = ManageUsersUseCase(SqlUserRepository(db))
    await uc.delete(user_id)
