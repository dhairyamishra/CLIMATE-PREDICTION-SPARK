"""
Application configuration using pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str = "climate"
    postgres_password: str = "climate_secret"
    postgres_db: str = "climate_db"
    postgres_host: str = "postgis"
    postgres_port: int = 5432

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "dev-api-key-change-me"
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:80"

    # Spark
    spark_master_url: str = "spark://spark-master:7077"

    # HDFS
    hdfs_namenode_host: str = "namenode"
    hdfs_namenode_port: int = 9000

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
