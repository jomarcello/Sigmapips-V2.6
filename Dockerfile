FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    build-essential \
    procps \
    git \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with error handling
RUN playwright install chromium || echo "Playwright browser installation failed, will attempt to continue"

# Copy application code (excluding .env in production)
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Amsterdam

# Document required environment variables
# Note: These should be set in Railway/Production environment
# ENV OPENAI_API_KEY=""
# ENV TAVILY_API_KEY=""

# Setup initial configuration
RUN chmod +x ./docker_setup.sh || echo "docker_setup.sh not found or not executable, skipping"
RUN if [ -f "./docker_setup.sh" ]; then ./docker_setup.sh; else echo "Skipping docker_setup.sh"; fi

# Expose port for FastAPI
EXPOSE 8000

# Command to run the application
# Create a startup script that runs both the FastAPI server and the Telegram bot
RUN echo '#!/bin/bash\n\
echo "Starting Trading Bot Services..."\n\
\n\
# First, stop any existing Telegram bot processes\n\
echo "Stopping any existing Telegram bot processes..."\n\
\n\
# Find and kill any Python processes that might be running our bot\n\
for pid in $(ps aux | grep -E "python|python3" | grep -E "trading_bot|main.py|telegram|bot|sigmapips" | grep -v grep | awk "{print \$2}"); do\n\
  echo "Killing process $pid"\n\
  kill -9 $pid 2>/dev/null || true\n\
done\n\
\n\
# Clear Telegram API sessions\n\
BOT_TOKEN=${TELEGRAM_BOT_TOKEN}\n\
if [ -n "$BOT_TOKEN" ]; then\n\
  echo "Clearing Telegram API sessions..."\n\
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" > /dev/null\n\
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates?timeout=1&offset=-1&limit=1" > /dev/null\n\
  sleep 2\n\
fi\n\
\n\
# Start the FastAPI server in the background\n\
python -m trading_bot.server & \n\
\n\
# Start the Telegram bot in the foreground\n\
python -m trading_bot.main\n\
' > /app/start.sh

RUN chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]
