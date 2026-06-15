import json
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.robot_command import RobotCommand
from src.frameworks.db.models import CommandLogModel


class AbstractCommandLogRepository(ABC):
    @abstractmethod
    async def save(self, command: RobotCommand) -> None: ...


class SqlCommandLogRepository(AbstractCommandLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def save(self, command: RobotCommand) -> None:
        model = CommandLogModel(
            id=command.id,
            user_id=command.user_id,
            command_type=command.command_type.value,
            payload=json.dumps(command.payload),
            acknowledged=command.acknowledged,
        )
        self._s.add(model)
        await self._s.commit()
