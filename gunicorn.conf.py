import multiprocessing
import logging

from src.config import settings
from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.gunicorn")

# Server socket
bind = f"0.0.0.0:{settings.API_MAIN_PORT}"
backlog = 2048
workers = multiprocessing.cpu_count()  

# Worker processes
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 30
keepalive = 2

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr

# Use settings LOG_LEVEL or default
if settings.ENVIRONMENT == "DEVELOPMENT":
    loglevel = "debug"
else:
    loglevel = "info"

access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "ramp-api"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Restart workers gracefully
graceful_timeout = 30
preload_app = False  # Set to True for faster worker spawning

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    logger.info(f"Gunicorn starting with {workers} workers in {settings.ENVIRONMENT} mode")
    logger.info(f"Binding to {bind}")

def when_ready(server):
    """Called just after the server is started."""
    logger.info(f"Gunicorn ready. Listening on {bind}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Workers: {workers}")
    logger.info(f"Log level: {loglevel}")

def on_exit(server):
    """Called just before exiting."""
    logger.info("Gunicorn shutting down")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    logger.info(f"Worker {worker.pid} received interrupt signal")

def worker_abort(worker):
    """Called when a worker times out."""
    logger.error(f"Worker {worker.pid} timed out")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    logger.debug(f"About to fork worker {worker}")

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    logger.info(f"Worker {worker.pid} spawned")

def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    logger.info(f"Worker {worker.pid} initialized")

def worker_exit(server, worker):
    """Called when a worker is exiting."""
    logger.info(f"Worker {worker.pid} exiting")