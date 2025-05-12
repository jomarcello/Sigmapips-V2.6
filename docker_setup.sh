#!/bin/bash
# Docker setup script for SigmaPips Trading Bot

# Log message for debugging
echo "Starting Docker setup for SigmaPips Trading Bot..."

# We don't need to install system packages or dependencies again
# as they are already installed in the Dockerfile

# Create necessary directories if they don't exist
echo "Creating necessary directories..."
mkdir -p data/cache
mkdir -p logs
mkdir -p tmp

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 data
chmod -R 755 logs
chmod -R 755 tmp

# Create empty __init__.py files if they don't exist
# This ensures Python can import from these directories
echo "Setting up Python package structure..."
touch trading_bot/__init__.py
touch trading_bot/services/__init__.py

# Create log files if they don't exist
echo "Creating log files..."
touch logs/app.log
touch logs/error.log

echo "Docker setup completed successfully." 
