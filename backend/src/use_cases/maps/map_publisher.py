import struct
import time

from src.domain.entities.map_data import MapMeta
from src.frameworks.ros.rosbridge_client import RosBridgeClient
from src.frameworks.storage.minio_client import MinioClient

# Пороги соответствуют дефолтным значениям nav2_map_server
_OCCUPIED_THRESH = 0.65
_FREE_THRESH = 0.25

MAP_TOPIC = "/map"
MAP_MSG_TYPE = "nav_msgs/msg/OccupancyGrid"


def _parse_pgm(data: bytes) -> tuple[int, int, int, list[int]]:
    """Парсит P5/P2 PGM, возвращает (width, height, maxval, pixels)."""
    buf = memoryview(data)
    pos = 0

    def read_token() -> str:
        nonlocal pos
        # пропускаем пробелы и комментарии
        while pos < len(buf):
            c = buf[pos]
            if c in (32, 9, 10, 13):  # ' ', '\t', '\n', '\r'
                pos += 1
            elif c == 35:  # '#'
                while pos < len(buf) and buf[pos] != 10:
                    pos += 1
            else:
                break
        start = pos
        while pos < len(buf) and buf[pos] not in (32, 9, 10, 13):
            pos += 1
        if pos == start:
            raise ValueError("Неожиданный конец PGM-файла")
        return bytes(buf[start:pos]).decode("ascii")

    magic = read_token()
    if magic not in ("P5", "P2"):
        raise ValueError(f"Неподдерживаемый формат: {magic!r}, ожидается P5 или P2")

    width = int(read_token())
    height = int(read_token())
    maxval = int(read_token())

    if magic == "P5":
        # после maxval ровно один пробельный байт-разделитель
        pos += 1
        n = width * height
        size = n * (2 if maxval > 255 else 1)
        raw = bytes(buf[pos : pos + size])
        if len(raw) < size:
            raise ValueError(f"PGM: недостаточно данных ({len(raw)}/{size} байт)")
        if maxval <= 255:
            pixels = list(raw)
        else:
            pixels = list(struct.unpack(f">{n}H", raw))
    else:  # P2 ASCII
        pixels = [int(read_token()) for _ in range(width * height)]

    return width, height, maxval, pixels


def _to_occupancy(pixels: list[int], maxval: int) -> list[int]:
    """Конвертирует пиксели PGM в значения OccupancyGrid (0 / 100 / -1)."""
    result: list[int] = []
    inv = 1.0 / maxval
    for p in pixels:
        occ = (maxval - p) * inv  # белый=0.0 (свободно), чёрный=1.0 (препятствие)
        if occ > _OCCUPIED_THRESH:
            result.append(100)
        elif occ < _FREE_THRESH:
            result.append(0)
        else:
            result.append(-1)
    return result


def _build_message(
    width: int,
    height: int,
    resolution: float,
    origin_x: float,
    origin_y: float,
    data: list[int],
) -> dict:
    now = time.time()
    sec = int(now)
    nanosec = int((now - sec) * 1e9)
    stamp = {"sec": sec, "nanosec": nanosec}
    return {
        "header": {"stamp": stamp, "frame_id": "map"},
        "info": {
            "map_load_time": stamp,
            "resolution": float(resolution),
            "width": width,
            "height": height,
            "origin": {
                "position": {"x": origin_x, "y": origin_y, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            },
        },
        "data": data,
    }


class MapPublisher:
    def __init__(self, storage: MinioClient, ros: RosBridgeClient) -> None:
        self._storage = storage
        self._ros = ros

    async def publish(self, meta: MapMeta) -> None:
        if not meta.file_key:
            raise ValueError("У карты нет PGM-файла для публикации")
        if not meta.resolution:
            raise ValueError("У карты не задано поле resolution")

        pgm_data = await self._storage.download("maps", meta.file_key)
        width, height, maxval, pixels = _parse_pgm(pgm_data)

        # PGM: строка 0 = верх; OccupancyGrid: строка 0 = нижний левый угол — переворачиваем
        rows = [pixels[r * width : (r + 1) * width] for r in range(height)]
        rows.reverse()
        flat = [p for row in rows for p in row]

        occupancy_data = _to_occupancy(flat, maxval)

        res = meta.resolution
        origin_x = -(width * res) / 2.0
        origin_y = -(height * res) / 2.0

        msg = _build_message(width, height, res, origin_x, origin_y, occupancy_data)

        # Transient Local QoS через latch=True — Nav2 получит карту даже если стартует позже
        await self._ros.advertise(MAP_TOPIC, MAP_MSG_TYPE, latch=True)
        await self._ros.publish(MAP_TOPIC, msg)
