"""
Application configuration management using Pydantic BaseSettings.
Loads environment variables from .env with fallback defaults.
"""

from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application Info
    PROJECT_NAME: str = "WelfareConnect Government Scheme Assistant"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database
    DATABASE_URL: str = "sqlite:///./welfareconnect.db"

    # Authentication & JWT
    JWT_SECRET: str = "placeholder-jwt-secret-key-must-be-changed-in-production-32-chars-min"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_IN_MINUTES: int = 1440

    # Vector Database (Pinecone)
    PINECONE_API_KEY: str = "placeholder-pinecone-api-key"
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "welfareconnect-schemes-index"
    PINECONE_DIMENSION: int = 1536
    PINECONE_METRIC: str = "cosine"

    # AI & Embeddings
    OPENAI_API_KEY: str = "placeholder-openai-api-key"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_COMPLETION_MODEL: str = "gpt-4o-mini"

    # Task Queue / Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    STORAGE_TYPE: str = "local"
    LOCAL_STORAGE_PATH: str = "./data/storage"
    S3_BUCKET_NAME: str = "placeholder-welfareconnect-bucket"
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY_ID: str = "placeholder-s3-key"
    # File Upload & Ingestion Constraints
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf"]
    ALLOWED_FILE_EXTENSIONS: List[str] = [".pdf"]

    # OCR & Ingestion Pipeline Configuration
    OCR_ENGINE: str = "auto"  # "auto", "tesseract", "fallback", "heuristic"
    OCR_CONFIDENCE_THRESHOLD: float = 70.0  # Under 70% confidence marks for administrator review
    OCR_MIN_WORD_THRESHOLD: int = 15  # Minimum native words before triggering OCR
    OCR_DPI: int = 200  # Resolution for rendering scanned pages
    OCR_LANGUAGES: str = "eng"
    MAX_PROCESSING_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SECONDS: float = 0.5


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
