import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.map_data import MapMeta
from src.domain.repositories.map_repository import AbstractMapRepository
from src.frameworks.db.models import MapModel


def _to_entity(m: MapModel) -> MapMeta:
    return MapMeta(
        id=m.id,
        name=m.name,
        description=m.description,
        created_by=m.created_by,
        map_type=m.map_type,
        file_key=m.file_key,
        geojson_key=m.geojson_key,
        thumbnail_key=m.thumbnail_key,
        width_meters=m.width_meters,
        height_meters=m.height_meters,
        resolution=m.resolution,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class SqlMapRepository(AbstractMapRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, map_id: uuid.UUID) -> MapMeta | None:
        result = await self._s.execute(select(MapModel).where(MapModel.id == map_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def create(self, meta: MapMeta) -> MapMeta:
        model = MapModel(
            id=meta.id, name=meta.name, description=meta.description,
            map_type=meta.map_type, file_key=meta.file_key, geojson_key=meta.geojson_key,
            thumbnail_key=meta.thumbnail_key, created_by=meta.created_by,
            width_meters=meta.width_meters, height_meters=meta.height_meters,
            resolution=meta.resolution,
        )
        self._s.add(model)
        await self._s.commit()
        await self._s.refresh(model)
        return _to_entity(model)

    async def update(self, meta: MapMeta) -> MapMeta:
        result = await self._s.execute(select(MapModel).where(MapModel.id == meta.id))
        model = result.scalar_one()
        model.name = meta.name
        model.description = meta.description
        model.geojson_key = meta.geojson_key
        model.width_meters = meta.width_meters
        model.height_meters = meta.height_meters
        await self._s.commit()
        await self._s.refresh(model)
        return _to_entity(model)

    async def delete(self, map_id: uuid.UUID) -> None:
        result = await self._s.execute(select(MapModel).where(MapModel.id == map_id))
        model = result.scalar_one_or_none()
        if model:
            await self._s.delete(model)
            await self._s.commit()

    async def list_all(self, map_type: str | None = None) -> list[MapMeta]:
        query = select(MapModel).order_by(MapModel.created_at.desc())
        if map_type is not None:
            query = query.where(MapModel.map_type == map_type)
        result = await self._s.execute(query)
        return [_to_entity(m) for m in result.scalars().all()]
