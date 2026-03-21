#!/bin/bash
# Test nginx configuration

echo "Testing nginx configuration..."

# Check if nginx.conf exists
if [ ! -f "nginx/nginx.conf" ]; then
    echo "❌ nginx/nginx.conf not found"
    exit 1
fi

# Check if default.conf exists
if [ ! -f "nginx/conf.d/default.conf" ]; then
    echo "❌ nginx/conf.d/default.conf not found"
    exit 1
fi

echo "✅ All nginx configuration files present"

# Test with docker
echo "Testing nginx configuration syntax with Docker..."
docker run --rm -v "$(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" -v "$(pwd)/nginx/conf.d:/etc/nginx/conf.d:ro" nginx:alpine nginx -t

echo "Configuration test complete."
