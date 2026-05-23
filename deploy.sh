#!/bin/bash
# Hostinger VPS deployment script
# Run once on your VPS after cloning the repo

set -e

echo "=== Deploying JAMB Blogger Agent from GHCR ==="

# 1. Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file missing. Creating from example..."
    cp .env.example .env
    echo "Fill in your credentials in .env then re-run this script."
    exit 1
fi

# 2. Create required dirs
mkdir -p db logs

# 3. Pull latest images from GitHub Container Registry
echo "Pulling latest Docker images..."
docker compose pull

# 4. Restart services
echo "Starting services..."
docker compose up -d --remove-orphans

echo ""
echo "=== Deployment Complete ==="
echo "Agent:  running (cron 06:00 WAT daily)"
echo "Admin:  http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f agent   # watch agent logs"
echo "  docker compose logs -f admin   # watch admin logs"
echo "  docker compose restart agent   # restart agent"
echo "  docker compose pull && docker compose up -d   # update to latest"
