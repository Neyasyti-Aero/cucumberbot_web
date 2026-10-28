import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.qr_code import QRCode
from src.domain.entities.user import UserRole
from src.frameworks.db.repositories.map_repo import SqlMapRepository
from src.frameworks.db.repositories.qr_repo import SqlQRRepository
from src.frameworks.db.session import get_db
from src.frameworks.security.rbac import current_user, require_role
from src.frameworks.storage.minio_client import get_minio_client
from src.use_cases.qr.qr_generator import (
    CreateQRInput,
    QRService,
    build_payload,
    landmarks_yaml,
    render_png,
    render_sheet_pdf,
    to_png_bytes,
)

router = APIRouter()

_SIZE_MM = Query(50.0, ge=15.0, le=180.0, description="Сторона QR при печати, мм")
_DPI = Query(300, ge=72, le=600)


class CreateQRRequest(BaseModel):
    label: str
    description: str = ""
    map_id: str
    x: float
    y: float
    theta: float = 0.0


class QRResponse(BaseModel):
    id: str
    label: str
    description: str
    map_id: str
    x: float
    y: float
    theta: float
    payload: str
    image_url: str


class SyncResponse(BaseModel):
    created: list[QRResponse]
    kept: list[QRResponse]
    orphaned: list[QRResponse]


def _qr_to_response(qr: QRCode) -> QRResponse:
    return QRResponse(
        id=str(qr.id), label=qr.label, description=qr.description,
        map_id=str(qr.map_id), x=qr.x, y=qr.y, theta=qr.theta,
        payload=build_payload(qr), image_url=f"/api/v1/qr/{qr.id}/image.png",
    )


def _service(db: AsyncSession) -> QRService:
    return QRService(SqlQRRepository(db), SqlMapRepository(db), get_minio_client())


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Некорректный идентификатор") from exc


@router.get("/{map_id}", response_model=list[QRResponse])
async def list_qr_for_map(
    map_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    qrs = await SqlQRRepository(db).get_by_map(_parse_uuid(map_id))
    return [_qr_to_response(q) for q in qrs]


@router.post("/", response_model=QRResponse, status_code=status.HTTP_201_CREATED)
async def create_qr(
    body: CreateQRRequest,
    _payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        qr = await _service(db).create(
            CreateQRInput(
                map_id=body.map_id, label=body.label, description=body.description,
                x=body.x, y=body.y, theta=body.theta,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _qr_to_response(qr)


@router.get("/{qr_id}/image.png")
async def get_qr_image(
    qr_id: str,
    size_mm: float = _SIZE_MM,
    dpi: int = _DPI,
    caption: bool = True,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    qr = await SqlQRRepository(db).get_by_id(_parse_uuid(qr_id))
    if not qr:
        raise HTTPException(status_code=404, detail="QR-код не найден")
    return Response(content=to_png_bytes(render_png(qr, size_mm, dpi, caption), dpi), media_type="image/png")


@router.post("/maps/{map_id}/sync", response_model=SyncResponse)
async def sync_qr_from_layout(
    map_id: str,
    _payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт метки для QR-точек из редактора карты. Уже существующие метки сохраняют id."""
    _parse_uuid(map_id)
    try:
        result = await _service(db).sync_from_layout(map_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SyncResponse(
        created=[_qr_to_response(q) for q in result.created],
        kept=[_qr_to_response(q) for q in result.kept],
        orphaned=[_qr_to_response(q) for q in result.orphaned],
    )


@router.get("/maps/{map_id}/sheet.pdf")
async def get_qr_sheet(
    map_id: str,
    size_mm: float = _SIZE_MM,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """PDF A4 для печати всех меток карты (печатать в масштабе 100%)."""
    qrs = await SqlQRRepository(db).get_by_map(_parse_uuid(map_id))
    try:
        pdf = render_sheet_pdf(sorted(qrs, key=lambda q: q.label), size_mm)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="qr_{map_id}.pdf"'},
    )


@router.get("/maps/{map_id}/landmarks.yaml")
async def get_landmarks(
    map_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Метки в кадре map для узла локализации по QR на роботе."""
    map_uuid = _parse_uuid(map_id)
    qrs = await SqlQRRepository(db).get_by_map(map_uuid)
    return Response(content=landmarks_yaml(map_uuid, qrs), media_type="application/x-yaml")


@router.delete("/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qr(
    qr_id: str,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SqlQRRepository(db)
    qr = await repo.get_by_id(_parse_uuid(qr_id))
    if not qr:
        raise HTTPException(status_code=404, detail="QR-код не найден")
    await get_minio_client().delete("maps", qr.image_key)
    await repo.delete(qr.id)
