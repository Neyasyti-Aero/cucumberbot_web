from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.user import User, UserRole


class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def create(self, email: str, hashed_password: str, role: UserRole) -> User: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...

    @abstractmethod
    async def delete(self, user_id: UUID) -> None: ...

    @abstractmethod
    async def list_all(self) -> list[User]: ...
