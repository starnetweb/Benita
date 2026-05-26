FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    curl \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent/ ./agent/

# Create directories for db and logs (mounted as volumes)
RUN mkdir -p /app/db /app/logs

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy cron job
COPY docker/crontab /etc/cron.d/blogger-agent
RUN chmod 0644 /etc/cron.d/blogger-agent

ENTRYPOINT ["/entrypoint.sh"]
