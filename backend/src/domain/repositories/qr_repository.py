from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.qr_code import QRCode


class AbstractQRRepository(ABC):
    @abstractmethod
    async def get_by_id(self, qr_id: UUID) -> QRCode | None: ...

    @abstractmethod
    async def get_by_map(self, map_id: UUID) -> list[QRCode]: ...

    @abstractmethod
    async def create(self, qr: QRCode) -> QRCode: ...

    @abstractmethod
    async def delete(self, qr_id: UUID) -> None: ...
