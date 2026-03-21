# logging_config.py
import logging
import os
from src.config import settings

ENV = settings.ENVIRONMENT.upper()

ENV_LEVEL_MAP = {
    "DEVELOPMENT": "DEBUG",
    "STAGING": "INFO",
    "PRODUCTION": "INFO",
}

def configure_logging():
    log_level = ENV_LEVEL_MAP.get(ENV, "INFO")

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Optional noise reduction
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("uvicorn.error").setLevel("INFO")
