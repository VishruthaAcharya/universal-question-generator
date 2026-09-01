from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = Field(
        "postgresql+psycopg://postgres:postgres@localhost:5432/question_generator",
        validation_alias="DATABASE_URL"
    )
    azure_openai_api_key: str = Field("", validation_alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field("", validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment_name: str = Field("gpt4-interview", validation_alias="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_api_version: str = Field("2024-12-01-preview", validation_alias="AZURE_OPENAI_API_VERSION")
    azure_openai_critic_deployment_name: str = Field("", validation_alias="AZURE_OPENAI_CRITIC_DEPLOYMENT_NAME")
    azure_openai_critic_api_version: str = Field("", validation_alias="AZURE_OPENAI_CRITIC_API_VERSION")
    backend_url: str = Field("http://localhost:8000", validation_alias="BACKEND_URL")
    max_upload_size_mb: int = Field(50, validation_alias="MAX_UPLOAD_SIZE_MB")
    max_ai_concurrency: int = Field(4, validation_alias="MAX_AI_CONCURRENCY")
    max_single_file_size_mb: int = Field(25, validation_alias="MAX_SINGLE_FILE_SIZE_MB")
    max_zip_size_mb: int = Field(50, validation_alias="MAX_ZIP_SIZE_MB")
    max_zip_extracted_size_mb: int = Field(150, validation_alias="MAX_ZIP_EXTRACTED_SIZE_MB")
    max_files_per_batch: int = Field(20, validation_alias="MAX_FILES_PER_BATCH")
    enable_extraction_cache: bool = Field(True, validation_alias="ENABLE_EXTRACTION_CACHE")
    confidence_calibration_log: bool = Field(False, validation_alias="CONFIDENCE_CALIBRATION_LOG")
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

