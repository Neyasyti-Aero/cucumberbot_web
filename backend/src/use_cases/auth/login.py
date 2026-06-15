from dataclasses import dataclass

from src.domain.repositories.user_repository import AbstractUserRepository
from src.frameworks.security.jwt_handler import TokenPair, create_token_pair
from src.frameworks.security.password import verify_password


@dataclass
class LoginInput:
    email: str
    password: str


@dataclass
class LoginOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(self, user_repo: AbstractUserRepository) -> None:
        self._repo = user_repo

    async def execute(self, data: LoginInput) -> LoginOutput:
        user = await self._repo.get_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            raise ValueError("Неверный email или пароль")
        if not user.is_active:
            raise PermissionError("Аккаунт деактивирован")

        pair: TokenPair = create_token_pair(str(user.id), user.role.value)
        return LoginOutput(access_token=pair.access_token, refresh_token=pair.refresh_token)
