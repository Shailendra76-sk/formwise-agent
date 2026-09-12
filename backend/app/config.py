from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Formwise Agent API"
    environment: str = "development"
    database_url: str = "sqlite:///./formwise.db"
    storage_root: str = "./private_storage"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    browser_headless: bool = True
    browser_timeout_ms: int = 15000
    browser_navigation_timeout_ms: int = 20000
    browser_max_sessions_per_user: int = 2
    browser_max_pages_per_session: int = 3
    browser_screenshot_enabled: bool = True
    browser_block_private_networks: bool = True
    browser_allow_local_demo_target: bool = False
    browser_demo_target_port: int = 5000
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    allow_legacy_user_header: bool = True
    serper_api_key: str = ""
    serper_url: str = "https://google.serper.dev/search"
    research_timeout_seconds: float = 20.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FORMWISE_", extra="ignore")

settings = Settings()
