from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class CommandType(str, Enum):
    PATROL = "patrol"
    COLLECT = "collect"
    RETURN_TO_BASE = "return_to_base"
    STOP = "stop"
    MOVE_TO = "move_to"


@dataclass
class RobotCommand:
    id: UUID
    user_id: UUID
    command_type: CommandType
    payload: dict
    issued_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False


@dataclass
class Telemetry:
    x: float
    y: float
    theta: float
    battery_percent: float
    task_status: str
    timestamp: float
