from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_ctx: int = 1024
    environment: str = "development"
    super_admin_emails: str = ""

    @property
    def super_admin_email_set(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.super_admin_emails.split(",")
            if email.strip()
        }

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
