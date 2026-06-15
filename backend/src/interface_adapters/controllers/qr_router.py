import io
import uuid

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.qr_code import QRCode
from src.domain.entities.user import UserRole
from src.frameworks.db.repositories.qr_repo import SqlQRRepository
from src.frameworks.db.session import get_db
from src.frameworks.security.rbac import current_user, require_role
from src.frameworks.storage.minio_client import get_minio_client

router = APIRouter()


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
    image_url: str | None = None


def _qr_to_response(qr: QRCode) -> QRResponse:
    return QRResponse(
        id=str(qr.id), label=qr.label, description=qr.description,
        map_id=str(qr.map_id), x=qr.x, y=qr.y, theta=qr.theta,
    )


@router.get("/{map_id}", response_model=list[QRResponse])
async def list_qr_for_map(
    map_id: str,
    _payload: dict = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = SqlQRRepository(db)
    qrs = await repo.get_by_map(uuid.UUID(map_id))
    return [_qr_to_response(q) for q in qrs]


@router.post("/", response_model=QRResponse, status_code=status.HTTP_201_CREATED)
async def create_qr(
    body: CreateQRRequest,
    payload: dict = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    qr_id = uuid.uuid4()
    qr_data = f"cucumberbot://qr/{qr_id}?x={body.x}&y={body.y}&theta={body.theta}&label={body.label}"

    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    minio = get_minio_client()
    image_key = f"qr/{qr_id}.png"
    await minio.upload(bucket="maps", key=image_key, data=image_bytes, content_type="image/png")

    repo = SqlQRRepository(db)
    qr = await repo.create(
        QRCode(
            id=qr_id, label=body.label, description=body.description,
            map_id=uuid.UUID(body.map_id), x=body.x, y=body.y,
            theta=body.theta, image_key=image_key,
        )
    )
    return _qr_to_response(qr)


@router.delete("/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qr(
    qr_id: str,
    _payload: dict = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SqlQRRepository(db)
    qr = await repo.get_by_id(uuid.UUID(qr_id))
    if not qr:
        raise HTTPException(status_code=404, detail="QR-код не найден")
    minio = get_minio_client()
    await minio.delete("maps", qr.image_key)
    await repo.delete(uuid.UUID(qr_id))
