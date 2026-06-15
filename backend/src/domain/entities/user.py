from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


@dataclass
class User:
    id: UUID
    email: str
    hashed_password: str
    role: UserRole
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
