# Centralized logger name prefix
API_MAIN_LOGGER_NAME_PREFIX = "api-main"

WORKER_MAIN_LOGGER_NAME_PREFIX = "worker-main"

# API PUBLIC PATHS NO AUTHORIZATION
PUBLIC_PATHS = ["/api/v1/health", "/", "/docs", "/redoc", "/openapi.json"]

SKIP_DB_FETCH_PATHS = [
    "/api/v1/health",
    "/api/v1/factories",
    "/api/v1/tenants",    
]

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"