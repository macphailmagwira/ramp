#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Starting api-main application entrypoint script..."

# ------------------------------
# Load environment variables
# ------------------------------
if [ -f .env ]; then
  echo "Loading environment variables from .env file..."
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([^[:space:]=#]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
      value=$(echo "$value" | sed 's/[[:space:]]*$//')
      value="${value%\"}"
      value="${value#\"}"
      value="${value%\'}"
      value="${value#\'}"
      export "$key=$value"
    fi
  done < .env
fi

# ------------------------------
# Normalize ENVIRONMENT
# ------------------------------
if [ -n "$ENVIRONMENT" ]; then
  export ENVIRONMENT=$(echo "$ENVIRONMENT" | tr '[:lower:]' '[:upper:]')
  echo -e "${GREEN}Normalized ENVIRONMENT to: ${ENVIRONMENT}${NC}"
fi

# ------------------------------
# Set defaults
# ------------------------------
PORT=${PORT:-8000}
HOST=${HOST:-"0.0.0.0"}
WORKERS=${WORKERS:-4}

# Set LOG_LEVEL based on ENVIRONMENT
if [ -z "$LOG_LEVEL" ]; then
  case "$ENVIRONMENT" in
    DEVELOPMENT)
      LOG_LEVEL="debug"
      ;;
    STAGING)
      LOG_LEVEL="info"
      ;;
    PRODUCTION)
      LOG_LEVEL="warning"
      ;;
    *)
      LOG_LEVEL="info"
      ;;
  esac
fi

# ------------------------------
# Verify Python packages are installed
# ------------------------------
echo -e "${YELLOW}Verifying required packages...${NC}"
if ! python -c "import uvicorn" 2>/dev/null; then
  echo -e "${RED}ERROR: uvicorn not found in Python path${NC}"
  echo "Python path: $(python -c 'import sys; print(sys.path)')"
  echo "Installed packages:"
  pip list | grep -E "(uvicorn|gunicorn|fastapi)" || true
  exit 1
fi

if ! python -c "import gunicorn" 2>/dev/null; then
  echo -e "${RED}ERROR: gunicorn not found in Python path${NC}"
  exit 1
fi

echo -e "${GREEN}All required packages verified!${NC}"

# ------------------------------
# Choose server based on environment
# ------------------------------
echo -e "${GREEN}Environment validation completed successfully!${NC}"

if [ "$ENVIRONMENT" = "PRODUCTION" ] || [ "$ENVIRONMENT" = "STAGING" ]; then
  # Use Gunicorn for production/staging
  echo -e "${GREEN}Starting with Gunicorn (production mode)${NC}"
  echo -e "  - Host: ${HOST}"
  echo -e "  - Port: ${PORT}"
  echo -e "  - Workers: ${WORKERS}"
  echo -e "  - Log level: ${LOG_LEVEL}"
  echo -e "  - Environment: ${ENVIRONMENT}"
  
  exec gunicorn src.main:app \
    --config gunicorn.conf.py \
    --bind ${HOST}:${PORT} \
    --workers ${WORKERS} \
    --log-level ${LOG_LEVEL}
else
  # Use Uvicorn with reload for development
  echo -e "${GREEN}Starting with Uvicorn (development mode)${NC}"
  echo -e "  - Host: ${HOST}"
  echo -e "  - Port: ${PORT}"
  echo -e "  - Log level: ${LOG_LEVEL}"
  echo -e "  - Environment: ${ENVIRONMENT}"
  
  # Always use python -m uvicorn for better compatibility
  exec python -m uvicorn src.main:app \
    --host ${HOST} \
    --port ${PORT} \
    --log-level ${LOG_LEVEL} \
    --reload
fi