#!/bin/bash
# Script om alle dependencies te installeren, inclusief yfinance

echo "Installing SigmaPips dependencies..."

# Update package information
echo "Updating package lists..."
apt-get update

# Install Python dependencies
echo "Installing required packages..."
pip install --upgrade pip
pip install python-telegram-bot>=20.3
pip install aiohttp>=3.8.4
pip install fastapi>=0.100.0
pip install uvicorn[standard]>=0.22.0
# Yahoo Finance removed - no longer used
# pip install yfinance==0.2.57
pip install cachetools>=5.5.0

# Install from requirements if available
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
fi

# Install browser automation dependencies
echo "Installing browser automation dependencies..."
pip install playwright>=1.40.0
playwright install chromium 

# Install Node.js dependencies for fallback
echo "Installing Node.js dependencies..."
if command -v npm &> /dev/null; then
    npm install playwright
    npx playwright install chromium
else
    echo "npm not found, skipping Node.js dependencies"
fi

echo "Done installing dependencies!" 
