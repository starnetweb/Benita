#!/bin/bash
set -e

echo "=== JAMB Blogger Agent Starting ==="

# Create directories if missing
mkdir -p /app/db /app/logs

# Always initialise the database (safe to run multiple times)
echo "Initialising database..."
cd /app && python -c "
import sys
sys.path.insert(0, 'agent')
import db
db.init_db()
print('Database ready:', db.get_db_path())
"

# Ensure DB and logs are world-readable/writable so admin container (www-data) can access
chmod -R 777 /app/db /app/logs 2>/dev/null || true

# Export all env vars so cron jobs can access them
printenv | grep -v "no_proxy" | grep -v "^_=" > /etc/environment

# Start cron daemon
echo "Starting cron daemon..."
cron

echo ""
echo "Agent ready. Scheduled: 05:00 UTC (06:00 WAT) daily."
echo "DB: ${DB_PATH:-/app/db/blogger.db}"
echo "Logs: ${LOG_PATH:-/app/logs/agent.log}"
echo ""

# Keep container alive — watch for manual trigger and tail logs
touch /app/logs/agent.log
rm -f /app/logs/.run_now

# Background watcher: if admin writes .run_now trigger file, run the agent
(
  while true; do
    if [ -f /app/logs/.run_now ]; then
      rm -f /app/logs/.run_now
      echo "[$(date)] Manual run triggered via admin panel" >> /app/logs/agent.log
      cd /app && python agent/agent.py >> /app/logs/agent.log 2>&1
    fi
    sleep 5
  done
) &

tail -f /app/logs/agent.log
