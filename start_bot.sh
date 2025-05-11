#!/bin/bash
# Start script voor SigmaPips Trading Bot

# Log header
echo "======================================================"
echo "          SIGMAPIPS TRADING BOT LAUNCHER              "
echo "======================================================"

# Update code van git repository als .git aanwezig is
if [ -d ".git" ]; then
    echo "Git repository gedetecteerd, code updaten..."
    git config --global --add safe.directory "$(pwd)"
    git pull
    echo "Code update voltooid."
else
    echo "Geen git repository gevonden, overslaan van code update."
fi

# Controleer of Python is geïnstalleerd
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is niet geïnstalleerd! Installeer Python 3 om de bot te gebruiken."
    exit 1
fi

# Zoek naar geïnstalleerde Python versies
PYTHON_COMMAND="python3"

# Check for specific Python versions in order of preference
if command -v python3.10 &> /dev/null; then
    PYTHON_COMMAND="python3.10"
elif command -v python3.9 &> /dev/null; then
    PYTHON_COMMAND="python3.9"
elif command -v python3.8 &> /dev/null; then
    PYTHON_COMMAND="python3.8"
fi

echo "Using Python command: $PYTHON_COMMAND"

# Create log directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo "Logs directory created."
fi

# Stop any existing bot instances - run with increased timeout
echo "Stopping any existing bot instances..."
$PYTHON_COMMAND stop_existing_bots.py

# Check if the stop script was successful
if [ $? -ne 0 ]; then
    echo "Warning: There was an issue stopping existing bot instances."
    echo "Waiting 10 seconds before continuing to ensure all processes are terminated..."
    sleep 10
fi

# Continue with virtual environment setup
VENV_DIR="venv"

# Controleer of virtuele omgeving bestaat
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtuele omgeving niet gevonden, aanmaken..."
    $PYTHON_COMMAND -m venv $VENV_DIR
    echo "Virtuele omgeving aangemaakt."
fi

# Activeer virtuele omgeving
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    source $VENV_DIR/Scripts/activate
else
    # Linux/Mac
    source $VENV_DIR/bin/activate
fi

# Installeer/update dependencies
echo "Dependencies installeren/updaten..."
pip install -r requirements.txt

# Verify critical packages are installed
echo "Verifying critical dependencies..."
python -c "import telegram" 2>/dev/null || { echo "Error: python-telegram-bot package is not properly installed!"; exit 1; }
python -c "import httpx" 2>/dev/null || { echo "Error: httpx package is not properly installed!"; exit 1; }
python -c "import psutil" 2>/dev/null || { echo "Error: psutil package is not properly installed!"; exit 1; }

# Run the stop script one more time to be absolutely sure
echo "Running final check to ensure no other bot instances are running..."
python stop_existing_bots.py

# Start de bot
echo "======================================================"
echo "          SIGMAPIPS TRADING BOT STARTEN               "
echo "======================================================"
python -m trading_bot.main

# Deactiveer virtuele omgeving (wordt alleen bereikt als bot wordt afgesloten)
deactivate
