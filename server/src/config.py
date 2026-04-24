from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ai_provider: str = "gemini"  # 'gemini' or 'anthropic'
    environment: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
