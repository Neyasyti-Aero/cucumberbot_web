from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.map_data import MapMeta
from src.domain.entities.user import UserRole
from src.frameworks.db.repositories.map_repo import SqlMapRepository
from src.frameworks.db.session import get_db
from src.frameworks.ros.rosbridge_client import get_rosbridge_client
from src.frameworks.security.rbac import current_user, require_role
from src.frameworks.storage.minio_client import get_minio_client
from src.use_cases.maps.map_publisher import MapPublisher
from src.use_cases.maps.map_service import CreateTemplateInput, MapService, UploadMapInput

router = APIRouter()


class MapResponse(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    map_type: str
    width_meters: float | None = None
    height_meters: float | None = None
    has_layout: bool = False


class TemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    map_type: str
    geojson: dict
    width_meters: float | None = None
    height_meters: float | None = None


class LayoutUpdateRequest(BaseModel):
    geojson: dict
    name: str | None = None
    description: str | None = None
    width_meters: float | None = None
    height_meters: float | None = None


def _to_response(m: MapMeta) -> MapResponse:
    return MapResponse(
        id=str(m.id),
        name=m.name,
        description=m.description,
        created_at=str(m.created_at),
        map_type=m.map_type,
        width_meters=m.width_meters,
        height_meters=m.height_meters,
        has_layout=m.geojson_key is not None,
    )


@router.get("/", response_model=list[MapResponse])
async def list_maps(
    map_type: str | None = None,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    maps = await service.get_all(map_type)
    return [_to_response(m) for m in maps]


@router.post("/", response_model=MapResponse, status_code=status.HTTP_201_CREATED)
async def upload_map(
    name: str = Form(...),
    description: str = Form(""),
    pgm_file: UploadFile | None = File(None),
    geojson_file: UploadFile | None = File(None),
    width_meters: float | None = Form(None),
    height_meters: float | None = Form(None),
    resolution: float | None = Form(None),
    payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    meta = await service.upload(
        UploadMapInput(
            name=name,
            description=description,
            user_id=payload["sub"],
            pgm_data=await pgm_file.read() if pgm_file else None,
            geojson_data=await geojson_file.read() if geojson_file else None,
            width_meters=width_meters,
            height_meters=height_meters,
            resolution=resolution,
        )
    )
    return _to_response(meta)


@router.post("/templates", response_model=MapResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreateRequest,
    payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    meta = await service.create_template(
        CreateTemplateInput(
            name=body.name,
            description=body.description,
            user_id=payload["sub"],
            map_type=body.map_type,
            geojson=body.geojson,
            width_meters=body.width_meters,
            height_meters=body.height_meters,
        )
    )
    return _to_response(meta)


@router.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    _payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    image_id = await service.upload_image(await file.read(), file.filename or "image.png")
    return {"key": image_id}


@router.get("/images/{image_id}")
async def get_image(
    image_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    try:
        data, content_type = await service.download_image(image_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Изображение не найдено") from exc
    return Response(content=data, media_type=content_type)


@router.put("/{map_id}/layout", response_model=MapResponse)
async def update_layout(
    map_id: str,
    body: LayoutUpdateRequest,
    _payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        service = MapService(SqlMapRepository(db), get_minio_client())
        meta = await service.update_layout(
            map_id,
            body.geojson,
            name=body.name,
            description=body.description,
            width_meters=body.width_meters,
            height_meters=body.height_meters,
        )
        return _to_response(meta)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{map_id}/layout")
async def get_layout(
    map_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        service = MapService(SqlMapRepository(db), get_minio_client())
        return await service.get_layout(map_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{map_id}/download-url")
async def get_download_url(
    map_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        service = MapService(SqlMapRepository(db), get_minio_client())
        url = await service.get_download_url(map_id)
        return {"url": url}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{map_id}/publish")
async def publish_map_to_robot(
    map_id: str,
    _payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    service = MapService(SqlMapRepository(db), get_minio_client())
    meta = await service.get_by_id(map_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Карта не найдена")

    publisher = MapPublisher(get_minio_client(), get_rosbridge_client())
    try:
        await publisher.publish(meta)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"status": "published", "topic": "/map", "map_id": map_id}


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_map(
    map_id: str,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        service = MapService(SqlMapRepository(db), get_minio_client())
        await service.delete(map_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
