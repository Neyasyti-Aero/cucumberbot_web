from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class MapMeta:
    id: UUID
    name: str
    description: str
    created_by: UUID
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    map_type: str = "geo"
    file_key: str | None = None
    geojson_key: str | None = None
    thumbnail_key: str | None = None
    width_meters: float | None = None
    height_meters: float | None = None
    resolution: float | None = None
