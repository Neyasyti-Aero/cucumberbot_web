import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User, UserRole
from src.domain.repositories.user_repository import AbstractUserRepository
from src.frameworks.db.models import UserModel


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        email=m.email,
        hashed_password=m.hashed_password,
        role=UserRole(m.role),
        is_active=m.is_active,
        created_at=m.created_at,
    )


class SqlUserRepository(AbstractUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._s.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._s.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def create(self, email: str, hashed_password: str, role: UserRole) -> User:
        model = UserModel(email=email, hashed_password=hashed_password, role=role.value)
        self._s.add(model)
        await self._s.commit()
        await self._s.refresh(model)
        return _to_entity(model)

    async def update(self, user: User) -> User:
        result = await self._s.execute(select(UserModel).where(UserModel.id == user.id))
        model = result.scalar_one()
        model.email = user.email
        model.hashed_password = user.hashed_password
        model.role = user.role.value
        model.is_active = user.is_active
        await self._s.commit()
        await self._s.refresh(model)
        return _to_entity(model)

    async def delete(self, user_id: uuid.UUID) -> None:
        result = await self._s.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        if model:
            await self._s.delete(model)
            await self._s.commit()

    async def list_all(self) -> list[User]:
        result = await self._s.execute(select(UserModel).order_by(UserModel.created_at))
        return [_to_entity(m) for m in result.scalars().all()]
