import uuid
from dataclasses import dataclass

from src.domain.entities.robot_command import CommandType, RobotCommand
from src.domain.repositories.user_repository import AbstractUserRepository
from src.frameworks.db.repositories.command_log_repo import AbstractCommandLogRepository
from src.frameworks.ros.rosbridge_client import RosBridgeClient


COMMAND_ROS_MAP: dict[CommandType, str] = {
    CommandType.PATROL: "/cucumberbot/patrol",
    CommandType.COLLECT: "/cucumberbot/collect",
    CommandType.RETURN_TO_BASE: "/cucumberbot/return_base",
    CommandType.STOP: "/cucumberbot/stop",
    CommandType.MOVE_TO: "/cucumberbot/move_to",
}


@dataclass
class SendCommandInput:
    user_id: str
    command_type: CommandType
    payload: dict


class SendCommandUseCase:
    def __init__(
        self,
        ros_client: RosBridgeClient,
        command_log_repo: AbstractCommandLogRepository,
    ) -> None:
        self._ros = ros_client
        self._log_repo = command_log_repo

    async def execute(self, data: SendCommandInput) -> RobotCommand:
        command = RobotCommand(
            id=uuid.uuid4(),
            user_id=uuid.UUID(data.user_id),
            command_type=data.command_type,
            payload=data.payload,
        )

        topic = COMMAND_ROS_MAP[data.command_type]
        await self._ros.publish(topic, data.payload)

        command.acknowledged = True
        await self._log_repo.save(command)
        return command
