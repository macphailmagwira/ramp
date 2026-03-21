import logging
from celery import Celery
from celery.signals import setup_logging

from src.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# BROKER CONFIGURATION
# ============================================================================

REDIS_HOST = settings.REDIS_HOST or "localhost"
REDIS_PORT = settings.REDIS_PORT or "6379"

BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
REDBEAT_REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = Celery("ramp", broker=BROKER_URL, backend=RESULT_BACKEND)

# ============================================================================
# LOGGING
# ============================================================================

@setup_logging.connect
def setup_celery_logging(**kwargs):
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("celery.worker.strategy").setLevel(logging.WARNING)
    logging.getLogger("kombu").setLevel(logging.INFO)

# ============================================================================
# CONFIGURATION
# ============================================================================

app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Worker
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_hijack_root_logger=False,

    # Beat
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=REDBEAT_REDIS_URL,
    redbeat_lock_timeout=3600,
)

# ============================================================================
# TASK DISCOVERY
# ============================================================================

app.autodiscover_tasks([
    "src.features.github",
])


logger.info(f"Celery ready — broker: {BROKER_URL}")