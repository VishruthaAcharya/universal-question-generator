from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/question_generator"
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt4-interview"
    azure_openai_api_version: str = "2024-12-01-preview"
    backend_url: str = "http://localhost:8000"
    max_upload_size_mb: int = 50
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
