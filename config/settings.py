"""Application configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Centralized application configuration"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # App
    APP_NAME: str = "ColdMail AI Pro"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = Field(default=False, alias="DEBUG")
    ENV: str = Field(default="development", alias="ENV")

    # Groq LLM
    GROQ_API_KEY: str = Field(default="", alias="GROQ_API_KEY")
    GROQ_MODEL: str = Field(default="openai/gpt-oss-20b", alias="GROQ_MODEL")
    GROQ_TEMPERATURE: float = Field(default=0.7, alias="GROQ_TEMPERATURE")
    GROQ_MAX_TOKENS: int = Field(default=800, alias="GROQ_MAX_TOKENS")
    # Opportunity extraction has its own tighter budget so large pasted job
    # descriptions do not exceed Groq's on-demand TPM limit.
    GROQ_EXTRACTION_MAX_INPUT_CHARS: int = Field(default=12000, alias="GROQ_EXTRACTION_MAX_INPUT_CHARS")
    GROQ_EXTRACTION_MAX_TOKENS: int = Field(default=1200, alias="GROQ_EXTRACTION_MAX_TOKENS")
    # Research guardrails: prevent a slow/blocked website from stalling the workflow.
    RESEARCH_HTTP_TIMEOUT: float = Field(default=8.0, alias="RESEARCH_HTTP_TIMEOUT")
    RESEARCH_MAX_CONCURRENCY: int = Field(default=4, alias="RESEARCH_MAX_CONCURRENCY")

    # SMTP
    SMTP_HOST: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, alias="SMTP_PORT")
    SMTP_USERNAME: str = Field(default="", alias="SMTP_USERNAME")
    SMTP_PASSWORD: str = Field(default="", alias="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, alias="SMTP_USE_TLS")
    SENDER_NAME: str = Field(default="", alias="SENDER_NAME")
    SENDER_EMAIL: str = Field(default="", alias="SENDER_EMAIL")

    # Rate Limiting
    MAX_EMAILS_PER_BATCH: int = Field(default=10, alias="MAX_EMAILS_PER_BATCH")
    DELAY_BETWEEN_EMAILS: int = Field(default=30, alias="DELAY_BETWEEN_EMAILS")
    MAX_DAILY_EMAILS: int = Field(default=20, alias="MAX_DAILY_EMAILS")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/coldmail",
        alias="DATABASE_URL"
    )

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ChromaDB
    CHROMA_PERSIST_DIR: str = Field(default="./chroma_db", alias="CHROMA_PERSIST_DIR")
    CHROMA_COLLECTION: str = Field(default="coldmail_memory", alias="CHROMA_COLLECTION")

    # Vector Embeddings
    EMBEDDING_MODEL: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # JWT
    JWT_SECRET: str = Field(default="your-secret-key-change-in-production", alias="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", alias="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, alias="JWT_EXPIRATION_HOURS")

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", alias="LOG_FORMAT")


# Global settings instance
settings = Settings()
