from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Formwise Agent API"
    environment: str = "development"
    database_url: str = "sqlite:///./formwise.db"
    storage_root: str = "./private_storage"
    max_upload_size_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FORMWISE_",
        extra="ignore",
    )


settings = Settings()
