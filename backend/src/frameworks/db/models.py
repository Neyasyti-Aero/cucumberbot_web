import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="operator")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MapModel(Base):
    __tablename__ = "maps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    map_type = Column(String(20), nullable=False, default="geo")
    file_key = Column(String(512), nullable=True)
    geojson_key = Column(String(512), nullable=True)
    thumbnail_key = Column(String(512), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    width_meters = Column(Float, nullable=True)
    height_meters = Column(Float, nullable=True)
    resolution = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class QRCodeModel(Base):
    __tablename__ = "qr_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(255), nullable=False)
    description = Column(Text, default="")
    map_id = Column(UUID(as_uuid=True), ForeignKey("maps.id", ondelete="CASCADE"), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    theta = Column(Float, nullable=False, default=0.0)
    image_key = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommandLogModel(Base):
    __tablename__ = "command_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    command_type = Column(String(100), nullable=False)
    payload = Column(Text, nullable=False, default="{}")
    acknowledged = Column(Boolean, nullable=False, default=False)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())


class TerminalLogModel(Base):
    __tablename__ = "terminal_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    command = Column(Text, nullable=False)
    output = Column(Text, nullable=False, default="")
    exit_code = Column(String(10), nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
