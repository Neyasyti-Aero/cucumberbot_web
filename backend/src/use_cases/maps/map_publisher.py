import io
import json
import time
import zipfile

from src.domain.entities.map_data import MapMeta
from src.frameworks.ros.rosbridge_client import RosBridgeClient
from src.frameworks.storage.minio_client import MinioClient
from src.use_cases.maps.nav2_map import (
    DEFAULT_RESOLUTION,
    MapYaml,
    Nav2Bundle,
    grid_to_ros_message,
    layout_to_nav2,
    parse_map_yaml,
    pgm_to_grid,
    validate_grid,
)

MAP_TOPIC = "/map"
MAP_MSG_TYPE = "nav_msgs/msg/OccupancyGrid"


def yaml_key_for(meta: MapMeta) -> str:
    return f"maps/{meta.id}/map.yaml"


class MapPublisher:
    def __init__(self, storage: MinioClient, ros: RosBridgeClient | None = None) -> None:
        self._storage = storage
        self._ros = ros

    async def build(self, meta: MapMeta, resolution: float | None = None) -> Nav2Bundle:
        """Собирает карту Nav2: из загруженного PGM (+YAML) или растеризацией GeoJSON-разметки."""
        if meta.file_key:
            pgm = await self._storage.download("maps", meta.file_key)
            try:
                map_yaml = parse_map_yaml(await self._storage.download("maps", yaml_key_for(meta)))
            except FileNotFoundError:
                if not meta.resolution:
                    raise ValueError("У карты нет map.yaml и не задано поле resolution") from None
                map_yaml = MapYaml(resolution=meta.resolution)
            grid = pgm_to_grid(pgm, map_yaml)
            return Nav2Bundle(pgm=pgm, yaml=map_yaml, grid=grid)

        if meta.geojson_key:
            geojson = json.loads(await self._storage.download("maps", meta.geojson_key))
            return layout_to_nav2(geojson, resolution=resolution or meta.resolution or DEFAULT_RESOLUTION)

        raise ValueError("У карты нет ни PGM-файла, ни разметки")

    async def validate(self, meta: MapMeta, resolution: float | None = None) -> dict:
        bundle = await self.build(meta, resolution)
        report = validate_grid(bundle.grid)
        report["warnings"] = bundle.warnings + report["warnings"]
        report["source"] = "pgm" if meta.file_key else "layout"
        return report

    async def export_zip(self, meta: MapMeta, resolution: float | None = None) -> bytes:
        """Архив map.pgm + map.yaml для `ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=map.yaml`."""
        bundle = await self.build(meta, resolution)
        bundle.yaml.image = "map.pgm"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("map.pgm", bundle.pgm)
            zf.writestr("map.yaml", bundle.yaml.dump())
        return buf.getvalue()

    async def publish(self, meta: MapMeta, resolution: float | None = None) -> dict:
        if self._ros is None:
            raise ConnectionError("Нет клиента rosbridge")
        bundle = await self.build(meta, resolution)
        report = validate_grid(bundle.grid)
        if not report["valid"]:
            raise ValueError("; ".join(report["errors"]))

        now = time.time()
        sec = int(now)
        stamp = {"sec": sec, "nanosec": int((now - sec) * 1e9)}
        msg = grid_to_ros_message(bundle.grid, stamp)

        # Transient Local QoS через latch=True — Nav2 получит карту даже если стартует позже
        await self._ros.advertise(MAP_TOPIC, MAP_MSG_TYPE, latch=True)
        await self._ros.publish(MAP_TOPIC, msg)
        report["warnings"] = bundle.warnings + report["warnings"]
        return report
