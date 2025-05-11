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

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

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
RUN chmod +x ./docker_setup.sh
RUN ./docker_setup.sh

# Expose port for FastAPI
EXPOSE 8000

# Command to run the application
CMD ["sh", "-c", "python -m trading_bot.main"]
