from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/question_generator"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    backend_url: str = "http://localhost:8000"
    max_upload_size_mb: int = 50
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
