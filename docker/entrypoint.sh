#!/bin/bash
set -e

echo "=== JAMB Blogger Agent Starting ==="

# Initialise database
echo "Initialising database..."
cd /app && python agent/db.py 2>&1 || python -c "import sys; sys.path.insert(0,'agent'); import db; db.init_db(); print('DB ready')"

# Export env vars to cron environment
printenv | grep -v "no_proxy" > /etc/environment

# Start cron daemon
echo "Starting cron..."
cron

echo "Agent ready. Cron scheduled for 05:00 UTC (06:00 WAT) daily."
echo "Logs: /app/logs/agent.log"

# Keep container alive and tail logs
tail -f /app/logs/agent.log 2>/dev/null || tail -f /dev/null
