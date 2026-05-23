#!/bin/bash
# Deploy script for Hostinger VPS
# Run this on the VPS after cloning the repo

set -e

echo "=== Deploying JAMB Blogger Agent ==="

# 1. Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your credentials."
    cp .env.example .env
    echo "Created .env from .env.example — please edit it before restarting."
    exit 1
fi

# 2. Create required dirs
mkdir -p db logs

# 3. Pull latest images and rebuild
docker compose pull 2>/dev/null || true
docker compose build --no-cache

# 4. Start services
docker compose up -d

echo ""
echo "=== Deployment Complete ==="
echo "Agent:  running (cron at 06:00 WAT daily)"
echo "Admin:  http://$(hostname -I | awk '{print $1}'):8080"
echo "Logs:   docker compose logs -f agent"
