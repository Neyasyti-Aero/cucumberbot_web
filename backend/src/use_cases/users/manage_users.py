import uuid
from dataclasses import dataclass

from src.domain.entities.user import User, UserRole
from src.domain.repositories.user_repository import AbstractUserRepository
from src.frameworks.security.password import hash_password


@dataclass
class CreateUserInput:
    email: str
    password: str
    role: UserRole = UserRole.OPERATOR


@dataclass
class UpdateUserInput:
    user_id: str
    email: str | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class ManageUsersUseCase:
    def __init__(self, user_repo: AbstractUserRepository) -> None:
        self._repo = user_repo

    async def create(self, data: CreateUserInput) -> User:
        existing = await self._repo.get_by_email(data.email)
        if existing:
            raise ValueError(f"Пользователь с email {data.email} уже существует")
        return await self._repo.create(
            email=data.email,
            hashed_password=hash_password(data.password),
            role=data.role,
        )

    async def get_all(self) -> list[User]:
        return await self._repo.list_all()

    async def get_by_id(self, user_id: str) -> User:
        user = await self._repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise ValueError("Пользователь не найден")
        return user

    async def update(self, data: UpdateUserInput) -> User:
        user = await self._repo.get_by_id(uuid.UUID(data.user_id))
        if not user:
            raise ValueError("Пользователь не найден")
        if data.email is not None:
            user.email = data.email
        if data.password is not None:
            user.hashed_password = hash_password(data.password)
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        return await self._repo.update(user)

    async def delete(self, user_id: str) -> None:
        await self._repo.delete(uuid.UUID(user_id))
