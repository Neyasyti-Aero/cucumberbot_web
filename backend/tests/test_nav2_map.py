import io
import json
import uuid
import zipfile

import pytest
import yaml

from src.domain.entities.map_data import MapMeta
from src.use_cases.maps.map_publisher import MapPublisher
from src.use_cases.maps.nav2_map import (
    MapYaml,
    cell_value,
    grid_to_ros_message,
    layout_points,
    layout_to_nav2,
    parse_map_yaml,
    parse_pgm,
    pgm_to_grid,
    validate_grid,
    write_pgm,
)


def _room(w: float, h: float, extra: list | None = None, mode: str = "relative") -> dict:
    features = [
        {
            "type": "Feature",
            "properties": {"featureType": "zone", "isRoom": True},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [w, 0], [w, h], [0, h], [0, 0]]]},
        }
    ]
    return {"type": "FeatureCollection", "properties": {"mapMode": mode}, "features": features + (extra or [])}


def _point(kind: str, x: float, y: float, label: str | None = None) -> dict:
    return {
        "type": "Feature",
        "properties": {"featureType": kind, "label": label},
        "geometry": {"type": "Point", "coordinates": [x, y]},
    }


def test_pgm_rows_are_flipped_to_bottom_origin():
    # 2x2: верхняя строка чёрная (занято), нижняя белая (свободно)
    pgm = write_pgm(2, 2, bytes([0, 0, 254, 254]))
    grid = pgm_to_grid(pgm, MapYaml(resolution=0.1))
    # строка 0 OccupancyGrid — нижняя строка картинки
    assert grid.data == [0, 0, 100, 100]


def test_trinary_thresholds_match_nav2_map_saver_values():
    pgm = write_pgm(3, 1, bytes([254, 0, 205]))
    grid = pgm_to_grid(pgm, MapYaml(resolution=0.05))
    assert grid.data == [0, 100, -1]


def test_negate_and_scale_modes():
    pgm = write_pgm(2, 1, bytes([0, 255]))
    assert pgm_to_grid(pgm, MapYaml(resolution=0.05, negate=True)).data == [0, 100]
    mid = write_pgm(1, 1, bytes([140]))  # occ ≈ 0.45
    value = pgm_to_grid(mid, MapYaml(resolution=0.05, mode="scale", free_thresh=0.25)).data[0]
    assert 0 < value < 100


def test_parse_map_yaml_roundtrip_and_errors():
    meta = MapYaml(resolution=0.05, origin=(-1.5, 2.0, 0.1))
    parsed = parse_map_yaml(meta.dump().encode())
    assert parsed.resolution == 0.05
    assert parsed.origin == (-1.5, 2.0, 0.1)
    with pytest.raises(ValueError):
        parse_map_yaml(b"origin: [0, 0, 0]\n")
    with pytest.raises(ValueError):
        parse_map_yaml(b"resolution: 0.05\nfree_thresh: 0.9\noccupied_thresh: 0.5\n")


def test_parse_pgm_ascii_and_truncated():
    assert parse_pgm(b"P2\n# c\n2 1\n255\n0 255\n") == (2, 1, 255, [0, 255])
    with pytest.raises(ValueError):
        parse_pgm(b"P5\n4 4\n255\n\x00\x00")


def test_layout_room_is_free_with_walls_and_beds_are_obstacles():
    bed = {
        "type": "Feature",
        "properties": {"featureType": "zone"},
        "geometry": {"type": "Polygon", "coordinates": [[[2, 2], [3, 2], [3, 6], [2, 6], [2, 2]]]},
    }
    grid = layout_to_nav2(_room(10, 8, [bed]), resolution=0.05, padding=0.5).grid

    # origin — левый нижний угол с учётом отступа; угол помещения = (0, 0) кадра map
    assert grid.origin == pytest.approx((-0.5, -0.5, 0.0))
    assert (grid.width, grid.height) == (220, 180)
    assert cell_value(grid, 5.0, 1.0) == 0  # внутри помещения
    assert cell_value(grid, 2.5, 4.0) == 100  # грядка
    assert cell_value(grid, -0.3, 4.0) == 100  # снаружи
    assert cell_value(grid, 0.0, 4.0) == 100  # стена
    assert cell_value(grid, 50, 50) is None

    report = validate_grid(grid)
    assert report["valid"], report
    assert report["cells"]["free"] > 0


def test_layout_warns_about_qr_inside_obstacle():
    bundle = layout_to_nav2(_room(4, 4, [_point("qr", 1, 1, "ok"), _point("qr", 10, 10, "outside")]))
    assert len(bundle.warnings) == 1
    assert "outside" in bundle.warnings[0]


def test_layout_geo_mode_projects_to_meters():
    lat, lng = 55.0, 37.0
    d_lat = 10 / 111319.49  # ≈ 10 м по широте
    geojson = _room(0, 0, mode="geo")
    geojson["features"][0]["geometry"]["coordinates"] = [
        [[lng, lat], [lng + 0.0002, lat], [lng + 0.0002, lat + d_lat], [lng, lat + d_lat], [lng, lat]]
    ]
    geojson["features"].append(_point("qr", lng + 0.0001, lat + d_lat / 2))
    grid = layout_to_nav2(geojson, resolution=0.1, padding=0).grid
    assert grid.height * grid.resolution == pytest.approx(10, abs=0.15)
    p = layout_points(geojson, "qr")[0]
    assert p["y"] == pytest.approx(5, abs=0.05)
    assert cell_value(grid, p["x"], p["y"]) == 0


def test_empty_layout_rejected():
    with pytest.raises(ValueError):
        layout_to_nav2({"type": "FeatureCollection", "features": []})


def test_exported_yaml_reloads_to_same_grid():
    bundle = layout_to_nav2(_room(3, 2))
    reloaded = pgm_to_grid(bundle.pgm, parse_map_yaml(bundle.yaml.dump().encode()))
    assert reloaded.data == bundle.grid.data
    assert reloaded.origin == bundle.grid.origin


def test_ros_message_shape():
    grid = layout_to_nav2(_room(2, 2), resolution=0.1).grid
    msg = grid_to_ros_message(grid, {"sec": 1, "nanosec": 0})
    assert msg["header"]["frame_id"] == "map"
    info = msg["info"]
    assert len(msg["data"]) == info["width"] * info["height"]
    assert info["origin"]["orientation"]["w"] == pytest.approx(1.0)
    assert all(-1 <= v <= 100 for v in msg["data"])


class _FakeStorage:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    async def download(self, bucket: str, key: str) -> bytes:
        if key not in self.files:
            raise FileNotFoundError(key)
        return self.files[key]


def _meta(**kwargs) -> MapMeta:
    return MapMeta(id=uuid.uuid4(), name="m", description="", created_by=uuid.uuid4(), **kwargs)


async def test_publisher_export_zip_from_layout():
    storage = _FakeStorage({"layout": json.dumps(_room(3, 3)).encode()})
    data = await MapPublisher(storage).export_zip(_meta(geojson_key="layout"), resolution=0.1)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert set(zf.namelist()) == {"map.pgm", "map.yaml"}
        y = yaml.safe_load(zf.read("map.yaml"))
        assert y["image"] == "map.pgm" and y["resolution"] == 0.1 and len(y["origin"]) == 3


async def test_publisher_uses_uploaded_yaml_origin():
    meta = _meta(file_key="pgm")
    storage = _FakeStorage({
        "pgm": write_pgm(2, 2, bytes([254] * 4)),
        f"maps/{meta.id}/map.yaml": b"image: x.pgm\nresolution: 0.05\norigin: [-3.0, 4.0, 0.0]\n",
    })
    bundle = await MapPublisher(storage).build(meta)
    assert bundle.grid.origin == (-3.0, 4.0, 0.0)


async def test_publisher_pgm_without_yaml_needs_resolution():
    meta = _meta(file_key="pgm")
    storage = _FakeStorage({"pgm": write_pgm(1, 1, bytes([254]))})
    with pytest.raises(ValueError):
        await MapPublisher(storage).build(meta)
