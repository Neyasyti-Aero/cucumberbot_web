from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.map_data import MapMeta


class AbstractMapRepository(ABC):
    @abstractmethod
    async def get_by_id(self, map_id: UUID) -> MapMeta | None: ...

    @abstractmethod
    async def create(self, meta: MapMeta) -> MapMeta: ...

    @abstractmethod
    async def update(self, meta: MapMeta) -> MapMeta: ...

    @abstractmethod
    async def delete(self, map_id: UUID) -> None: ...

    @abstractmethod
    async def list_all(self, map_type: str | None = None) -> list[MapMeta]: ...
