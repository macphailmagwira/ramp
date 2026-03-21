# Nginx Configuration for StitchSense

This directory contains the Nginx configuration for the StitchSense platform.

## Structure

- `nginx.conf` - Main Nginx configuration file
- `conf.d/default.conf` - Server blocks and routing configuration for all services
- `test-config.sh` - Script to test nginx configuration syntax

## Services Routing

The configuration routes traffic to three main services:

### 1. API Backend (api.stitchsense.ai)

- Routes to `api-main:8000` container
- Endpoints:
  - `/api/*` - Main API endpoints
  - `/ws/*` - WebSocket connections
  - `/docs`, `/redoc`, `/openapi.json` - API documentation
  - `/health` - Health check endpoint
  - `/api/admin/*` - Admin endpoints with stricter rate limiting

### 2. Web Dashboard (app.stitchsense.ai)

- Routes to `web-dashboard:3000` container
- Next.js application with server-side rendering
- Endpoints:
  - `/` - Main application
  - `/_next/*` - Next.js static assets
  - `/api/*` - Next.js API routes
  - `/api/health` - Health check endpoint

### 3. PWA Display App (display.stitchsense.ai)

- Routes to `pwa-display-app:80` container
- Progressive Web App for factory floor displays
- Endpoints:
  - `/` - Main PWA application
  - `/sw.js` - Service worker
  - `/manifest.json` - PWA manifest
  - `/assets/*` - Static assets
  - `/health` - Health check endpoint

## Security Features

- SSL/TLS termination with Let's Encrypt certificates
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Rate limiting for API and admin endpoints
- CORS configuration for cross-origin requests

## Testing Configuration

Run the test script to verify nginx configuration syntax:

```bash
./nginx/test-config.sh
```

## Docker Integration

The configuration is designed to work with Docker Compose. The nginx service in `docker-compose.yml` mounts these configuration files:

- `./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`
- `./nginx/conf.d:/etc/nginx/conf.d:ro`

## SSL Certificates

SSL certificates are managed by Certbot and stored in Docker volumes:

- `certbot-etc:/etc/letsencrypt`
- `certbot-var:/var/lib/letsencrypt`

The certificates are automatically renewed by the Certbot container.
