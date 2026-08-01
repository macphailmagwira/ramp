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
    """Configure the root logger.

    The default level is derived from the current environment (development → DEBUG,
    staging/production → INFO).  For ad‑hoc debugging you can override the level
    with the ``LOG_LEVEL`` environment variable.  Any value accepted by the
    standard ``logging`` module (e.g. ``DEBUG``, ``INFO``, ``WARNING``) is
    respected.
    """
    # Base level from environment mapping
    log_level = ENV_LEVEL_MAP.get(ENV, "INFO")

    # Environment variable override – useful for temporary debug runs
    env_override = os.getenv("LOG_LEVEL")
    if env_override:
        # Normalise to uppercase and validate against known levels
        env_override = env_override.upper()
        if env_override in logging._nameToLevel:
            log_level = env_override
        else:
            logging.warning(
                "Invalid LOG_LEVEL '%s' – falling back to %s", env_override, log_level
            )

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Optional noise reduction
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("uvicorn.error").setLevel("INFO")
