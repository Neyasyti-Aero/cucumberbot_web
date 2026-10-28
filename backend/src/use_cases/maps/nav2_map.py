"""Формирование карт в формате ROS 2 / Nav2.

Поддерживает два источника:
  * загруженная пара map.pgm + map.yaml (формат nav2_map_server);
  * GeoJSON-разметка из веб-редактора — растеризуется в occupancy grid.

Конвертация пикселей повторяет nav2_map_server (map_io.cpp), поэтому карта,
опубликованная из веба, совпадает с той, что загрузит map_server из pgm+yaml.
"""

import math
import struct
from dataclasses import dataclass, field

import yaml
from PIL import Image, ImageDraw

# Значения, которые пишет nav2_map_saver в режиме trinary
PGM_FREE = 254
PGM_OCCUPIED = 0
PGM_UNKNOWN = 205

DEFAULT_RESOLUTION = 0.05
DEFAULT_OCCUPIED_THRESH = 0.65
# 0.196: пиксель 205 (unknown) даёт occ=0.19607 и не попадает в free.
# С nav2-дефолтом 0.25 unknown-область превратилась бы в свободную.
DEFAULT_FREE_THRESH = 0.196

# Ограничение размера: OccupancyGrid уходит в rosbridge одним JSON-сообщением
MAX_CELLS = 16_000_000
LARGE_GRID_WARN_CELLS = 4_000_000

EARTH_RADIUS = 6378137.0


@dataclass
class OccupancyGrid:
    width: int
    height: int
    resolution: float
    origin: tuple[float, float, float]  # x, y, yaw — левый нижний угол карты в кадре map
    data: list[int]  # row-major, строка 0 = нижняя (как в nav_msgs/OccupancyGrid)
    frame_id: str = "map"


@dataclass
class MapYaml:
    resolution: float
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    negate: bool = False
    occupied_thresh: float = DEFAULT_OCCUPIED_THRESH
    free_thresh: float = DEFAULT_FREE_THRESH
    mode: str = "trinary"
    image: str = "map.pgm"

    def dump(self) -> str:
        return yaml.safe_dump(
            {
                "image": self.image,
                "mode": self.mode,
                "resolution": float(self.resolution),
                "origin": [float(v) for v in self.origin],
                "negate": int(self.negate),
                "occupied_thresh": float(self.occupied_thresh),
                "free_thresh": float(self.free_thresh),
            },
            sort_keys=False,
            default_flow_style=None,
        )


@dataclass
class Nav2Bundle:
    pgm: bytes
    yaml: MapYaml
    grid: OccupancyGrid
    warnings: list[str] = field(default_factory=list)


# ---------- PGM / YAML ----------


def parse_pgm(data: bytes) -> tuple[int, int, int, list[int]]:
    """Парсит P5/P2 PGM, возвращает (width, height, maxval, pixels). Строка 0 = верх."""
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
    if width <= 0 or height <= 0 or not 0 < maxval < 65536:
        raise ValueError(f"PGM: некорректный заголовок {width}x{height}, maxval={maxval}")

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


def write_pgm(width: int, height: int, pixels: bytes) -> bytes:
    header = f"P5\n# CREATOR: cucumberbot_web\n{width} {height}\n255\n".encode("ascii")
    return header + pixels


def parse_map_yaml(data: bytes) -> MapYaml:
    try:
        raw = yaml.safe_load(data.decode("utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ValueError(f"Некорректный YAML карты: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("YAML карты должен быть словарём")

    if "resolution" not in raw:
        raise ValueError("В YAML карты нет поля resolution")
    origin = raw.get("origin", [0.0, 0.0, 0.0])
    if not isinstance(origin, (list, tuple)) or len(origin) not in (2, 3):
        raise ValueError("Поле origin должно быть списком [x, y, yaw]")
    origin = [float(v) for v in origin] + [0.0] * (3 - len(origin))

    mode = str(raw.get("mode", "trinary"))
    if mode not in ("trinary", "scale", "raw"):
        raise ValueError(f"Неизвестный mode {mode!r}: ожидается trinary, scale или raw")

    meta = MapYaml(
        resolution=float(raw["resolution"]),
        origin=(origin[0], origin[1], origin[2]),
        negate=bool(int(raw.get("negate", 0))),
        occupied_thresh=float(raw.get("occupied_thresh", DEFAULT_OCCUPIED_THRESH)),
        free_thresh=float(raw.get("free_thresh", DEFAULT_FREE_THRESH)),
        mode=mode,
        image=str(raw.get("image", "map.pgm")),
    )
    _check_yaml(meta)
    return meta


def _check_yaml(meta: MapYaml) -> None:
    if not (meta.resolution > 0 and math.isfinite(meta.resolution)):
        raise ValueError("resolution должен быть положительным числом")
    if not all(math.isfinite(v) for v in meta.origin):
        raise ValueError("origin содержит некорректные значения")
    if not 0.0 <= meta.free_thresh < meta.occupied_thresh <= 1.0:
        raise ValueError("Должно выполняться 0 <= free_thresh < occupied_thresh <= 1")


def pgm_to_grid(pgm: bytes, meta: MapYaml) -> OccupancyGrid:
    """Конвертирует PGM в OccupancyGrid так же, как nav2_map_server::loadMapFromFile."""
    _check_yaml(meta)
    width, height, maxval, pixels = parse_pgm(pgm)
    if width * height > MAX_CELLS:
        raise ValueError(f"Карта слишком большая: {width}x{height} (максимум {MAX_CELLS} ячеек)")

    occ_t, free_t = meta.occupied_thresh, meta.free_thresh
    inv = 1.0 / maxval
    # таблица на все значения пикселя — быстрее, чем считать на каждую ячейку
    lut: list[int] = []
    for p in range(maxval + 1):
        if meta.mode == "raw":
            lut.append(p if p <= 100 else -1)
            continue
        occ = p * inv if meta.negate else (maxval - p) * inv
        if occ > occ_t:
            lut.append(100)
        elif occ < free_t:
            lut.append(0)
        elif meta.mode == "trinary":
            lut.append(-1)
        else:  # scale
            lut.append(round(99 * (occ - free_t) / (occ_t - free_t)))

    # PGM: строка 0 = верх; OccupancyGrid: строка 0 = низ
    data: list[int] = []
    for r in range(height - 1, -1, -1):
        data.extend(lut[p] for p in pixels[r * width : (r + 1) * width])

    return OccupancyGrid(width=width, height=height, resolution=meta.resolution, origin=meta.origin, data=data)


# ---------- GeoJSON-разметка редактора ----------


class LayoutFrame:
    """Переводит координаты GeoJSON редактора в метры кадра map (REP-103: x — вправо/восток, y — вверх/север).

    relative: координаты уже в метрах ([x, y], угол помещения = (0, 0)).
    geo: [lng, lat] проецируются на касательную плоскость в юго-западном углу разметки.
    """

    def __init__(self, geojson: dict) -> None:
        self.mode = (geojson.get("properties") or {}).get("mapMode", "relative")
        self.lat0 = self.lng0 = 0.0
        if self.mode == "geo":
            pts = [p for f in geojson.get("features", []) for p in _iter_coords(f.get("geometry") or {})]
            if pts:
                self.lng0 = min(p[0] for p in pts)
                self.lat0 = min(p[1] for p in pts)
        self._k = math.cos(math.radians(self.lat0)) * EARTH_RADIUS * math.pi / 180.0
        self._m = EARTH_RADIUS * math.pi / 180.0

    def to_map(self, coord: list[float] | tuple[float, float]) -> tuple[float, float]:
        if self.mode != "geo":
            return float(coord[0]), float(coord[1])
        return (coord[0] - self.lng0) * self._k, (coord[1] - self.lat0) * self._m


def _iter_coords(geometry: dict):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Point":
        yield coords
    elif gtype == "LineString":
        yield from coords
    elif gtype == "Polygon":
        for ring in coords:
            yield from ring


def _feature_type(feature: dict) -> str:
    return (feature.get("properties") or {}).get("featureType", "zone")


def layout_points(geojson: dict, feature_type: str) -> list[dict]:
    """Точечные объекты разметки (qr, waypoint) в координатах кадра map."""
    frame = LayoutFrame(geojson)
    result = []
    for f in geojson.get("features", []):
        geom = f.get("geometry") or {}
        if _feature_type(f) != feature_type or geom.get("type") != "Point":
            continue
        x, y = frame.to_map(geom["coordinates"])
        result.append({"x": x, "y": y, "label": (f.get("properties") or {}).get("label")})
    return result


def layout_to_nav2(
    geojson: dict,
    resolution: float = DEFAULT_RESOLUTION,
    padding: float = 0.5,
    wall_thickness: float = 0.1,
) -> Nav2Bundle:
    """Растеризует разметку редактора в карту Nav2.

    * помещение (zone с isRoom) — свободная область, контур — стена, снаружи — препятствие;
    * грядки (zone без isRoom) — препятствия;
    * дорожки, точки, база, QR, подложки — не влияют на проходимость.
    """
    if not resolution > 0:
        raise ValueError("resolution должен быть положительным")

    frame = LayoutFrame(geojson)
    warnings: list[str] = []
    rooms: list[list[tuple[float, float]]] = []
    obstacles: list[list[tuple[float, float]]] = []
    all_pts: list[tuple[float, float]] = []

    for f in geojson.get("features", []):
        ftype = _feature_type(f)
        geom = f.get("geometry") or {}
        if ftype == "image":
            continue
        pts = [frame.to_map(c) for c in _iter_coords(geom)]
        all_pts.extend(pts)
        if ftype == "zone" and geom.get("type") == "Polygon" and len(pts) >= 3:
            ring = [frame.to_map(c) for c in geom["coordinates"][0]]
            if (f.get("properties") or {}).get("isRoom"):
                rooms.append(ring)
            else:
                obstacles.append(ring)

    if not all_pts:
        raise ValueError("Разметка пуста — нечего конвертировать в карту")

    bounds_pts = [p for ring in rooms for p in ring] if rooms else all_pts
    if not rooms:
        warnings.append("В разметке нет помещения: границей карты считается габарит всех объектов")

    min_x = min(p[0] for p in bounds_pts) - padding
    min_y = min(p[1] for p in bounds_pts) - padding
    max_x = max(p[0] for p in bounds_pts) + padding
    max_y = max(p[1] for p in bounds_pts) + padding

    width = math.ceil((max_x - min_x) / resolution)
    height = math.ceil((max_y - min_y) / resolution)
    if width * height > MAX_CELLS:
        raise ValueError(
            f"Карта {width}x{height} ячеек слишком большая — увеличьте resolution (сейчас {resolution} м)"
        )

    def px(p: tuple[float, float]) -> tuple[float, float]:
        # PIL: y вниз, строка 0 = верхний край карты (max_y)
        return (p[0] - min_x) / resolution, (max_y - p[1]) / resolution

    wall_px = max(1, round(wall_thickness / resolution))
    img = Image.new("L", (width, height), PGM_OCCUPIED if rooms else PGM_FREE)
    draw = ImageDraw.Draw(img)

    if rooms:
        for ring in rooms:
            draw.polygon([px(p) for p in ring], fill=PGM_FREE)
        for ring in rooms:
            draw.line([px(p) for p in ring], fill=PGM_OCCUPIED, width=wall_px, joint="curve")
    else:
        draw.rectangle([0, 0, width - 1, height - 1], outline=PGM_OCCUPIED, width=wall_px)

    for ring in obstacles:
        draw.polygon([px(p) for p in ring], fill=PGM_OCCUPIED)

    meta = MapYaml(resolution=resolution, origin=(min_x, min_y, 0.0))
    pgm = write_pgm(width, height, img.tobytes())
    grid = pgm_to_grid(pgm, meta)

    for kind in ("qr", "base", "waypoint"):
        for p in layout_points(geojson, kind):
            if cell_value(grid, p["x"], p["y"]) != 0:
                name = p["label"] or kind
                warnings.append(f"Объект «{name}» ({p['x']:.2f}, {p['y']:.2f}) стоит вне свободной зоны")

    return Nav2Bundle(pgm=pgm, yaml=meta, grid=grid, warnings=warnings)


# ---------- Проверка и сообщение ROS ----------


def cell_value(grid: OccupancyGrid, x: float, y: float) -> int | None:
    """Значение ячейки по координатам кадра map (yaw origin не учитывается), None — вне карты."""
    col = math.floor((x - grid.origin[0]) / grid.resolution)
    row = math.floor((y - grid.origin[1]) / grid.resolution)
    if not (0 <= col < grid.width and 0 <= row < grid.height):
        return None
    return grid.data[row * grid.width + col]


def validate_grid(grid: OccupancyGrid) -> dict:
    """Проверяет, что сетка корректна для nav_msgs/OccupancyGrid и пригодна для Nav2."""
    errors: list[str] = []
    warnings: list[str] = []

    if grid.width <= 0 or grid.height <= 0:
        errors.append("Нулевой размер карты")
    if len(grid.data) != grid.width * grid.height:
        errors.append(f"Размер data ({len(grid.data)}) не равен width*height ({grid.width * grid.height})")
    if not (grid.resolution > 0 and math.isfinite(grid.resolution)):
        errors.append("Некорректный resolution")
    if not all(math.isfinite(v) for v in grid.origin):
        errors.append("Некорректный origin")
    if any(v < -1 or v > 100 for v in grid.data):
        errors.append("Значения ячеек должны быть в диапазоне -1..100")

    free = sum(1 for v in grid.data if v == 0)
    unknown = sum(1 for v in grid.data if v == -1)
    occupied = len(grid.data) - free - unknown
    total = max(1, len(grid.data))

    if free == 0:
        errors.append("На карте нет свободных ячеек — Nav2 не сможет построить маршрут")
    if grid.resolution > 0.1:
        warnings.append(f"Грубое разрешение {grid.resolution} м/пикс — проходы между грядками могут «слипнуться»")
    if grid.resolution < 0.01:
        warnings.append(f"Очень мелкое разрешение {grid.resolution} м/пикс — карта будет тяжёлой для costmap")
    if unknown / total > 0.5:
        warnings.append("Больше половины карты — неизвестная область")
    if len(grid.data) > LARGE_GRID_WARN_CELLS:
        warnings.append(f"Большая карта ({len(grid.data)} ячеек): публикация через rosbridge может занять время")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "width": grid.width,
        "height": grid.height,
        "resolution": grid.resolution,
        "origin": list(grid.origin),
        "size_meters": [grid.width * grid.resolution, grid.height * grid.resolution],
        "cells": {"free": free, "occupied": occupied, "unknown": unknown},
        "frame_id": grid.frame_id,
    }


def yaw_to_quaternion(yaw: float) -> dict:
    return {"x": 0.0, "y": 0.0, "z": math.sin(yaw / 2.0), "w": math.cos(yaw / 2.0)}


def grid_to_ros_message(grid: OccupancyGrid, stamp: dict) -> dict:
    """nav_msgs/msg/OccupancyGrid для rosbridge."""
    return {
        "header": {"stamp": stamp, "frame_id": grid.frame_id},
        "info": {
            "map_load_time": stamp,
            "resolution": float(grid.resolution),
            "width": grid.width,
            "height": grid.height,
            "origin": {
                "position": {"x": float(grid.origin[0]), "y": float(grid.origin[1]), "z": 0.0},
                "orientation": yaw_to_quaternion(grid.origin[2]),
            },
        },
        "data": grid.data,
    }
