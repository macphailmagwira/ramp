import json
import logging.config
from pathlib import Path
from typing import List, Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENVIRONMENT: Literal["DEVELOPMENT", "STAGING", "PRODUCTION"] = "DEVELOPMENT"

    # Gunicorn workers
    WORKERS: int = 2

    API_MAIN_PORT: int = 8000

    # -----------------------------
    # Database
    # -----------------------------
    DATABASE_URL: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[str] = None
    DB_NAME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None


    # -----------------------------
    # GitHub OAuth
    # -----------------------------
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: Optional[str] = None
    GITHUB_APP_NAME: str = "Ramp"

    # -----------------------------
    # Redis
    # -----------------------------
    REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None

    # -----------------------------
    # SQS (Staging & Production only)
    # -----------------------------
    SQS_DEFAULT_QUEUE_URL: Optional[str] = None
    SQS_DEFAULT_QUEUE_ARN: Optional[str] = None
    S3_EVENTS_QUEUE_URL: Optional[str] = None
    S3_EVENTS_QUEUE_ARN: Optional[str] = None
    # -----------------------------
    # AWS Cognito Authentication
    # -----------------------------
    COGNITO_REGION: str = "ap-southeast-1"
    COGNITO_USER_POOL_ID: Optional[str] = None
    COGNITO_APP_CLIENT_ID: Optional[str] = None

    # Derived (computed after load)
    JWKS_URL: Optional[str] = None
    ISSUER: Optional[str] = None

    # -----------------------------
    # AWS S3 Configuration
    # -----------------------------
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-southeast-1"
    S3_BUCKET_NAME: Optional[str] = None

    # -----------------------------
    # API
    # -----------------------------
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Ramp API Main"
    FRONTEND_URL: str = "http://localhost:3000"


    # -----------------------------
    # CORS
    # -----------------------------
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",

    ]

    DEBUG: bool = False

    def __init__(self, **values):
        super().__init__(**values)

        # ---------------------------------------------
        # Build DATABASE_URL if not provided
        # ---------------------------------------------
        if not self.DATABASE_URL and self.DB_HOST:
            db_user = self.DB_USER or "stitchsense_admin"
            db_password = self.DB_PASSWORD or "default_password"
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{db_user}:{db_password}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )


        # ---------------------------------------------
        # Validate GitHub OAuth Configuration
        # ---------------------------------------------
        if self.GITHUB_CLIENT_ID and not self.GITHUB_CLIENT_SECRET:
            logging.warning(
                "GITHUB_CLIENT_ID is set but GITHUB_CLIENT_SECRET is missing. "
                "GitHub OAuth login may fail."
            )

        if self.GITHUB_CLIENT_ID and not self.GITHUB_REDIRECT_URI:
            logging.warning(
                "GITHUB_CLIENT_ID is set but GITHUB_REDIRECT_URI is missing."
            )    

        # ---------------------------------------------
        # Build REDIS_URL if not provided
        # ---------------------------------------------
        if not self.REDIS_URL and self.REDIS_HOST:
            self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

        # ---------------------------------------------
        # Build JWKS + ISSUER for Cognito
        # ---------------------------------------------
        if self.COGNITO_USER_POOL_ID:
            self.JWKS_URL = (
                f"https://cognito-idp.{self.COGNITO_REGION}.amazonaws.com/"
                f"{self.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
            )
            self.ISSUER = (
                f"https://cognito-idp.{self.COGNITO_REGION}.amazonaws.com/"
                f"{self.COGNITO_USER_POOL_ID}"
            )

        # ---------------------------------------------
        # Validate AWS S3 Configuration
        # ---------------------------------------------
        if self.AWS_ACCESS_KEY_ID and not self.S3_BUCKET_NAME:
            logging.warning(
                "AWS_ACCESS_KEY_ID is set but S3_BUCKET_NAME is missing. "
                "S3 upload features may not work properly."
            )
        # Validate SQS settings for non-dev environments
        # ---------------------------------------------
        if self.ENVIRONMENT in ["STAGING", "PRODUCTION"]:
            if not self.SQS_DEFAULT_QUEUE_URL:
                logging.warning(
                    f"SQS_S3_EVENTS_QUEUE_URL not set for {self.ENVIRONMENT} environment"
                )
            if not self.SQS_DEFAULT_QUEUE_ARN:
                logging.warning(
                    f"SQS_S3_EVENTS_QUEUE_ARN not set for {self.ENVIRONMENT} environment"
                )

        # ---------------------------------------------
        # Logger
        # ---------------------------------------------
        config_file = Path("logger.json")
        if config_file.exists():
            with open(config_file, "r") as f:
                config = json.load(f)
                logging.config.dictConfig(config)
        else:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )