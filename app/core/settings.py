from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    """This class gets environment variables from .env file 
    """
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env",
                                    env_file_encoding="utf-8", extra="ignore")
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    PRODUCTS_CACHE_TTL_SECONDS: int = 60
    RATE_LIMIT_REQUEST: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")

    @property
    def REDIS_URL(self) -> str:
        return (
            f"redis://{self.REDIS_HOST}:"
            f"{self.REDIS_PORT}/{self.REDIS_DB}"
        )
settings = Settings() #type: ignore
