#!/bin/bash
# Simple script to test the simplified calendar service

# Set environment variables
export CALENDAR_FALLBACK="true"  # Enable fallback mode if API calls fail
export DEBUG="true"  # Enable detailed logging

echo "====================================="
echo "Simplified Calendar Service Test"
echo "====================================="
echo ""
echo "Environment variables:"
echo "CALENDAR_FALLBACK: $CALENDAR_FALLBACK"
echo "DEBUG: $DEBUG"
echo ""
echo "Running test..."
echo ""

# Run the test
python test_calendar_config.py

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test completed successfully!"
else
    echo ""
    echo "❌ Test failed! Check the logs for details."
fi

echo ""
echo "=====================================" 