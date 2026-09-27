from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    allow_sqlite_for_tests: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://japanesemastery.vercel.app",
    ]
    import_directory: str = "data/imports"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is required. Use a Neon PostgreSQL connection string."
            )
        if self.database_url.startswith("sqlite"):
            if self.allow_sqlite_for_tests:
                return self.database_url
            raise RuntimeError(
                "SQLite is not supported for the app. Configure Neon PostgreSQL in DATABASE_URL."
            )
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url
        raise RuntimeError("DATABASE_URL must be a PostgreSQL/Neon URL.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
