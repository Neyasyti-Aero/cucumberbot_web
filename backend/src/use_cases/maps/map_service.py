import json
import mimetypes
import os
import uuid
from dataclasses import dataclass

from src.domain.entities.map_data import MapMeta
from src.domain.repositories.map_repository import AbstractMapRepository
from src.frameworks.storage.minio_client import MinioClient


@dataclass
class UploadMapInput:
    name: str
    description: str
    user_id: str
    pgm_data: bytes | None = None
    yaml_data: bytes | None = None
    geojson_data: bytes | None = None
    width_meters: float | None = None
    height_meters: float | None = None
    resolution: float | None = None


@dataclass
class CreateTemplateInput:
    name: str
    description: str
    user_id: str
    map_type: str
    geojson: dict
    width_meters: float | None = None
    height_meters: float | None = None


class MapService:
    def __init__(self, map_repo: AbstractMapRepository, storage: MinioClient) -> None:
        self._repo = map_repo
        self._storage = storage

    async def upload(self, data: UploadMapInput) -> MapMeta:
        map_id = uuid.uuid4()
        file_key = None
        geojson_key = None

        if data.pgm_data:
            file_key = f"maps/{map_id}/map.pgm"
            await self._storage.upload(
                bucket="maps", key=file_key, data=data.pgm_data, content_type="image/x-portable-graymap"
            )

        if data.geojson_data:
            geojson_key = f"maps/{map_id}/layout.geojson"
            await self._storage.upload(
                bucket="maps", key=geojson_key, data=data.geojson_data, content_type="application/geo+json"
            )

        meta = MapMeta(
            id=map_id,
            name=data.name,
            description=data.description,
            created_by=uuid.UUID(data.user_id),
            map_type="geo",
            file_key=file_key,
            geojson_key=geojson_key,
            width_meters=data.width_meters,
            height_meters=data.height_meters,
            resolution=data.resolution,
        )
        return await self._repo.create(meta)

    async def create_template(self, data: CreateTemplateInput) -> MapMeta:
        map_id = uuid.uuid4()
        geojson_key = f"maps/{map_id}/layout.geojson"
        await self._storage.upload(
            bucket="maps", key=geojson_key, data=json.dumps(data.geojson).encode("utf-8"), content_type="application/geo+json"
        )

        meta = MapMeta(
            id=map_id,
            name=data.name,
            description=data.description,
            created_by=uuid.UUID(data.user_id),
            map_type=data.map_type,
            file_key=None,
            geojson_key=geojson_key,
            width_meters=data.width_meters,
            height_meters=data.height_meters,
        )
        return await self._repo.create(meta)

    async def update_layout(
        self, map_id: str, geojson: dict, name: str | None = None, description: str | None = None,
        width_meters: float | None = None, height_meters: float | None = None,
    ) -> MapMeta:
        meta = await self._repo.get_by_id(uuid.UUID(map_id))
        if not meta:
            raise ValueError("Карта не найдена")

        geojson_key = meta.geojson_key or f"maps/{meta.id}/layout.geojson"
        await self._storage.upload(
            bucket="maps", key=geojson_key, data=json.dumps(geojson).encode("utf-8"), content_type="application/geo+json"
        )

        meta.geojson_key = geojson_key
        if name is not None:
            meta.name = name
        if description is not None:
            meta.description = description
        if width_meters is not None:
            meta.width_meters = width_meters
        if height_meters is not None:
            meta.height_meters = height_meters

        return await self._repo.update(meta)

    async def get_layout(self, map_id: str) -> dict:
        meta = await self._repo.get_by_id(uuid.UUID(map_id))
        if not meta or not meta.geojson_key:
            raise ValueError("Шаблон карты не найден")
        data = await self._storage.download("maps", meta.geojson_key)
        return json.loads(data)

    async def upload_image(self, data: bytes, filename: str) -> str:
        ext = (os.path.splitext(filename)[1] or ".png").lower()

        # Convert first page of PDF to PNG on the backend
        if ext == ".pdf":
            import fitz  # PyMuPDF
            pdf = fitz.open(stream=data, filetype="pdf")
            page = pdf.load_page(0)
            pix = page.get_pixmap(dpi=150)
            data = pix.tobytes("png")
            pdf.close()
            ext = ".png"
            filename = os.path.splitext(filename)[0] + ".png"

        image_id = f"{uuid.uuid4()}{ext}"
        content_type = mimetypes.guess_type(filename)[0] or "image/png"
        await self._storage.upload(bucket="maps", key=f"images/{image_id}", data=data, content_type=content_type)
        return image_id

    async def download_image(self, image_id: str) -> tuple[bytes, str]:
        data = await self._storage.download("maps", f"images/{image_id}")
        content_type = mimetypes.guess_type(image_id)[0] or "application/octet-stream"
        return data, content_type

    async def get_all(self, map_type: str | None = None) -> list[MapMeta]:
        return await self._repo.list_all(map_type)

    async def get_download_url(self, map_id: str) -> str:
        meta = await self._repo.get_by_id(uuid.UUID(map_id))
        if not meta or not meta.file_key:
            raise ValueError("Карта не найдена")
        return await self._storage.presigned_url("maps", meta.file_key)

    async def delete(self, map_id: str) -> None:
        meta = await self._repo.get_by_id(uuid.UUID(map_id))
        if not meta:
            raise ValueError("Карта не найдена")
        if meta.file_key:
            await self._storage.delete("maps", meta.file_key)
        if meta.geojson_key:
            await self._storage.delete("maps", meta.geojson_key)
        await self._repo.delete(uuid.UUID(map_id))
