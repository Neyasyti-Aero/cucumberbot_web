from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class QRCode:
    id: UUID
    label: str
    map_id: UUID
    x: float
    y: float
    theta: float
    image_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
