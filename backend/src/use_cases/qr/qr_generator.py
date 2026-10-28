"""Генерация QR-меток для локализации робота.

Метка кодирует свой id и позу в кадре map. Координаты совпадают с кадром карты,
которую отдаёт /maps/{id}/nav2.zip и публикует /maps/{id}/publish.
"""

import io
import json
import math
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

import qrcode
import yaml
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_Q

from src.domain.entities.qr_code import QRCode
from src.domain.repositories.map_repository import AbstractMapRepository
from src.domain.repositories.qr_repository import AbstractQRRepository
from src.frameworks.storage.minio_client import MinioClient
from src.use_cases.maps.nav2_map import layout_points

PAYLOAD_SCHEME = "cucumberbot://qr/v1"
# Точки разметки ближе этого расстояния считаются одной и той же меткой (id не меняется)
SYNC_MATCH_DISTANCE = 0.05

MM_PER_INCH = 25.4
A4_MM = (210.0, 297.0)
SHEET_MARGIN_MM = 10.0

_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian, fonts-dejavu-core
    "DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def build_payload(qr: QRCode) -> str:
    """Содержимое QR: id метки и её поза в кадре map.

    Подпись и id карты в payload не входят: чем короче данные, тем крупнее модули кода
    и надёжнее распознавание камерой. Привязка id → карта есть в landmarks.yaml.
    """
    query = urlencode(
        {
            "x": f"{qr.x:.3f}",
            "y": f"{qr.y:.3f}",
            "theta": f"{qr.theta:.4f}",
        }
    )
    return f"{PAYLOAD_SCHEME}/{qr.id}?{query}"


def render_png(qr: QRCode, size_mm: float = 50.0, dpi: int = 300, caption: bool = True) -> Image.Image:
    """QR в физическом размере size_mm при печати с указанным dpi, с подписью снизу."""
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, border=4, box_size=1)
    code.add_data(build_payload(qr))
    code.make(fit=True)
    modules = code.modules_count + 2 * code.border

    target_px = round(size_mm / MM_PER_INCH * dpi)
    code.box_size = max(1, target_px // modules)
    img = code.make_image(fill_color="black", back_color="white").get_image().convert("L")
    if img.width != target_px:
        img = img.resize((target_px, target_px), Image.NEAREST)
    if not caption:
        return img

    font_size = max(12, target_px // 12)
    title, subtitle = _font(font_size), _font(max(10, font_size * 2 // 3))
    lines = [(qr.label, title), (f"x={qr.x:.2f}  y={qr.y:.2f}  θ={math.degrees(qr.theta):.0f}°", subtitle)]
    text_h = sum(f.size for _, f in lines) + font_size // 2 * len(lines)

    canvas = Image.new("L", (target_px, target_px + text_h), 255)
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    y = target_px
    for text, font in lines:
        w = draw.textlength(text, font=font)
        draw.text(((target_px - w) / 2, y), text, fill=0, font=font)
        y += font.size + font_size // 2
    return canvas


def render_sheet_pdf(codes: list[QRCode], size_mm: float = 50.0, dpi: int = 300) -> bytes:
    """Лист A4 для печати: метки в сетке, при печати 100% размер QR равен size_mm."""
    if not codes:
        raise ValueError("Нет QR-меток для печати")

    def mm(v: float) -> int:
        return round(v / MM_PER_INCH * dpi)

    page_w, page_h = mm(A4_MM[0]), mm(A4_MM[1])
    margin, gap = mm(SHEET_MARGIN_MM), mm(5)
    tiles = [render_png(qr, size_mm, dpi) for qr in codes]
    tile_w = max(t.width for t in tiles)
    tile_h = max(t.height for t in tiles)
    cols = max(1, (page_w - 2 * margin + gap) // (tile_w + gap))
    rows = max(1, (page_h - 2 * margin + gap) // (tile_h + gap))
    if tile_w > page_w - 2 * margin or tile_h > page_h - 2 * margin:
        raise ValueError(f"Метка {size_mm} мм не помещается на лист A4")

    pages: list[Image.Image] = []
    per_page = cols * rows
    for start in range(0, len(tiles), per_page):
        page = Image.new("L", (page_w, page_h), 255)
        draw = ImageDraw.Draw(page)
        for i, tile in enumerate(tiles[start : start + per_page]):
            x = margin + (i % cols) * (tile_w + gap)
            y = margin + (i // cols) * (tile_h + gap)
            page.paste(tile, (x, y))
            # тонкая рамка-линия реза
            draw.rectangle([x - 2, y - 2, x + tile_w + 1, y + tile_h + 1], outline=200, width=1)
        pages.append(page)

    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:], resolution=dpi)
    return buf.getvalue()


def to_png_bytes(img: Image.Image, dpi: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue()


def landmarks_yaml(map_id: uuid.UUID, codes: list[QRCode]) -> str:
    """Список меток для узла локализации на роботе (кадр map)."""
    return yaml.safe_dump(
        {
            "frame_id": "map",
            "map_id": str(map_id),
            "payload_scheme": PAYLOAD_SCHEME,
            "landmarks": [
                {"id": str(q.id), "label": q.label, "x": q.x, "y": q.y, "theta": q.theta} for q in codes
            ],
        },
        allow_unicode=True,
        sort_keys=False,
    )


@dataclass
class CreateQRInput:
    map_id: str
    label: str
    x: float
    y: float
    theta: float = 0.0
    description: str = ""


@dataclass
class SyncResult:
    created: list[QRCode]
    kept: list[QRCode]
    orphaned: list[QRCode]  # есть в БД, но точки на карте больше нет — не удаляем, метка могла быть напечатана


class QRService:
    def __init__(self, qr_repo: AbstractQRRepository, map_repo: AbstractMapRepository, storage: MinioClient) -> None:
        self._qr = qr_repo
        self._maps = map_repo
        self._storage = storage

    async def create(self, data: CreateQRInput) -> QRCode:
        map_id = uuid.UUID(data.map_id)
        if not await self._maps.get_by_id(map_id):
            raise ValueError("Карта не найдена")
        qr_id = uuid.uuid4()
        qr = QRCode(
            id=qr_id, label=data.label, description=data.description, map_id=map_id,
            x=data.x, y=data.y, theta=data.theta, image_key=f"qr/{qr_id}.png",
        )
        # архивная копия; для печати картинка рендерится на лету в нужном размере
        await self._storage.upload(
            bucket="maps", key=qr.image_key, data=to_png_bytes(render_png(qr), 300), content_type="image/png"
        )
        return await self._qr.create(qr)

    async def sync_from_layout(self, map_id: str) -> SyncResult:
        """Создаёт метки для QR-точек, расставленных в редакторе карты."""
        meta = await self._maps.get_by_id(uuid.UUID(map_id))
        if not meta or not meta.geojson_key:
            raise ValueError("У карты нет разметки")
        geojson = json.loads(await self._storage.download("maps", meta.geojson_key))
        points = layout_points(geojson, "qr")

        existing = await self._qr.get_by_map(meta.id)
        unmatched = list(existing)
        created: list[QRCode] = []
        kept: list[QRCode] = []
        for n, p in enumerate(points, start=1):
            match = next(
                (q for q in unmatched if math.hypot(q.x - p["x"], q.y - p["y"]) <= SYNC_MATCH_DISTANCE), None
            )
            if match:
                unmatched.remove(match)
                kept.append(match)
                continue
            created.append(
                await self.create(
                    CreateQRInput(
                        map_id=map_id, label=p["label"] or f"QR-{len(existing) + n:03d}",
                        x=round(p["x"], 3), y=round(p["y"], 3),
                    )
                )
            )
        return SyncResult(created=created, kept=kept, orphaned=unmatched)
