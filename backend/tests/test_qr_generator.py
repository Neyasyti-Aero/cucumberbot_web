import uuid
from urllib.parse import parse_qs, urlparse

import yaml

from src.domain.entities.qr_code import QRCode
from src.use_cases.qr.qr_generator import (
    PAYLOAD_SCHEME,
    QRService,
    build_payload,
    landmarks_yaml,
    render_png,
    render_sheet_pdf,
)


def _qr(label: str = "Грядка 1 & 2", x: float = 1.5, y: float = -2.25, map_id: uuid.UUID | None = None) -> QRCode:
    return QRCode(
        id=uuid.uuid4(), label=label, map_id=map_id or uuid.uuid4(), x=x, y=y, theta=1.5708, image_key="k"
    )


def test_payload_is_parsable():
    qr = _qr()
    payload = build_payload(qr)
    assert payload.startswith(f"{PAYLOAD_SCHEME}/{qr.id}?")
    q = parse_qs(urlparse(payload).query)
    assert "label" not in q and "map" not in q
    assert float(q["x"][0]) == 1.5 and float(q["y"][0]) == -2.25


def test_payload_fits_small_qr_version():
    import qrcode

    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
    code.add_data(build_payload(_qr(x=-123.456, y=789.012)))
    code.make(fit=True)
    assert code.version <= 8  # 49 модулей: ≈0.9 мм на модуль при метке 50 мм


def test_png_has_physical_size():
    img = render_png(_qr(), size_mm=50, dpi=300, caption=False)
    assert img.size == (591, 591)  # 50 мм при 300 dpi
    assert render_png(_qr(), size_mm=50, dpi=300).height > 591


def test_sheet_pdf_paginates():
    pdf = render_sheet_pdf([_qr(f"QR-{i}") for i in range(20)], size_mm=50)
    assert pdf.startswith(b"%PDF")
    assert b"/Count 2" in pdf  # 3x4 метки на A4 → 20 меток = 2 страницы


def test_landmarks_yaml():
    qr = _qr()
    data = yaml.safe_load(landmarks_yaml(qr.map_id, [qr]))
    assert data["frame_id"] == "map"
    assert data["landmarks"][0]["id"] == str(qr.id)


class _Repo:
    def __init__(self, items: list[QRCode]) -> None:
        self.items = items

    async def get_by_map(self, map_id):
        return [q for q in self.items if q.map_id == map_id]

    async def create(self, qr):
        self.items.append(qr)
        return qr


class _Maps:
    def __init__(self, meta) -> None:
        self.meta = meta

    async def get_by_id(self, map_id):
        return self.meta if map_id == self.meta.id else None


class _Storage:
    def __init__(self, layout: bytes) -> None:
        self.layout = layout
        self.uploaded: list[str] = []

    async def download(self, bucket, key):
        return self.layout

    async def upload(self, bucket, key, data, content_type=""):
        self.uploaded.append(key)


async def test_sync_from_layout_keeps_existing_ids():
    import json

    from src.domain.entities.map_data import MapMeta

    meta = MapMeta(id=uuid.uuid4(), name="m", description="", created_by=uuid.uuid4(), geojson_key="g")
    layout = {
        "type": "FeatureCollection",
        "properties": {"mapMode": "relative"},
        "features": [
            {"type": "Feature", "properties": {"featureType": "qr", "label": "A"},
             "geometry": {"type": "Point", "coordinates": [1.0, 2.0]}},
            {"type": "Feature", "properties": {"featureType": "qr"},
             "geometry": {"type": "Point", "coordinates": [5.0, 5.0]}},
        ],
    }
    existing = _qr("A", 1.01, 2.0, meta.id)
    stale = _qr("old", 9.0, 9.0, meta.id)
    repo = _Repo([existing, stale])
    service = QRService(repo, _Maps(meta), _Storage(json.dumps(layout).encode()))

    result = await service.sync_from_layout(str(meta.id))
    assert result.kept == [existing]
    assert result.orphaned == [stale]
    assert len(result.created) == 1 and (result.created[0].x, result.created[0].y) == (5.0, 5.0)
