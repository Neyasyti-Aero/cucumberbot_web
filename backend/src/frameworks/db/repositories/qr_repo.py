import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.qr_code import QRCode
from src.domain.repositories.qr_repository import AbstractQRRepository
from src.frameworks.db.models import QRCodeModel


def _to_entity(m: QRCodeModel) -> QRCode:
    return QRCode(
        id=m.id,
        label=m.label,
        map_id=m.map_id,
        x=m.x,
        y=m.y,
        theta=m.theta,
        image_key=m.image_key,
        description=m.description,
        created_at=m.created_at,
    )


class SqlQRRepository(AbstractQRRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, qr_id: uuid.UUID) -> QRCode | None:
        result = await self._s.execute(select(QRCodeModel).where(QRCodeModel.id == qr_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def get_by_map(self, map_id: uuid.UUID) -> list[QRCode]:
        result = await self._s.execute(select(QRCodeModel).where(QRCodeModel.map_id == map_id))
        return [_to_entity(m) for m in result.scalars().all()]

    async def create(self, qr: QRCode) -> QRCode:
        model = QRCodeModel(
            id=qr.id, label=qr.label, description=qr.description,
            map_id=qr.map_id, x=qr.x, y=qr.y, theta=qr.theta, image_key=qr.image_key,
        )
        self._s.add(model)
        await self._s.commit()
        await self._s.refresh(model)
        return _to_entity(model)

    async def delete(self, qr_id: uuid.UUID) -> None:
        result = await self._s.execute(select(QRCodeModel).where(QRCodeModel.id == qr_id))
        model = result.scalar_one_or_none()
        if model:
            await self._s.delete(model)
            await self._s.commit()
