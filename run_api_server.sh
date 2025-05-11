#!/bin/bash
# Script to run the FastAPI server locally for testing

# Set environment variables
export PORT=8000
export HOST="0.0.0.0"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

echo "Starting FastAPI server on $HOST:$PORT"
echo "API documentation available at http://$HOST:$PORT/docs"
echo "Health check endpoint at http://$HOST:$PORT/health"
echo "Press Ctrl+C to stop the server"

# Run the FastAPI server
python -m trading_bot.server 