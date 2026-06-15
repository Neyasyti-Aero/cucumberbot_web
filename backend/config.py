from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CucumberBot API"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/cucumberbot"
    database_sync_url: str = "postgresql://postgres:postgres@db:5432/cucumberbot"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    rosbridge_url: str = "ws://rosbridge:9090"
    rosbridge_reconnect_interval: float = 5.0

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_maps: str = "maps"
    minio_bucket_logs: str = "logs"
    minio_secure: bool = False

    default_admin_email: str = "admin@cucumberbot.io"
    default_admin_password: str = "Admin1234!"

    terminal_allowed_commands: list[str] = [
        "ls", "cat", "echo", "pwd", "env",
        "rostopic", "rosnode", "rosservice", "rosparam",
        "ros2", "ping",
    ]
    terminal_timeout_seconds: int = 30
    terminal_sandbox_dir: str = "/app/sandbox"


settings = Settings()
