#!/bin/bash

# Set environment variables for GMT+8 timezone
export TZ="Asia/Singapore"
echo "Setting timezone to GMT+8 (Asia/Singapore)"
echo "Current time in GMT+8: $(date)"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Install required Python packages if not already installed
echo "Checking for required Python packages..."
pip3 install -q requests beautifulsoup4 pytz

# Clean up any old HTML files to ensure fresh data
if [ -f "forexfactory_calendar.html" ]; then
    echo "Removing old HTML file..."
    rm forexfactory_calendar.html
fi

# Force Python to use GMT+8 timezone
export PYTHONTZ="Asia/Singapore"

# Run the script
echo "Running ForexFactory calendar automation (GMT+8 timezone)..."
TZ="Asia/Singapore" python3 get_today_events.py

SCRIPT_EXIT_CODE=$?

# Check if the script ran successfully
if [ $SCRIPT_EXIT_CODE -eq 0 ]; then
    echo "Automation completed successfully!"
    
    # Find the most recently created output files
    LATEST_JSON=$(find . -name "forex_factory_data_*.json" -type f -mmin -5 | sort | tail -n 1)
    
    if [ -n "$LATEST_JSON" ]; then
        # Extract date from filename
        LATEST_DATE=$(echo "$LATEST_JSON" | grep -o "[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}")
        LATEST_TXT="forex_factory_events_${LATEST_DATE}.txt"
        
        if [ -f "$LATEST_TXT" ]; then
            echo ""
            echo "Complete Events List (GMT+8 timezone):"
            echo "================="
            cat "$LATEST_TXT"
        else
            echo "Warning: Events text file not found: $LATEST_TXT"
        fi
    else
        echo "Warning: No output files were created in the last 5 minutes."
        # Check if any files were created previously
        JSON_FILES=$(find . -name "forex_factory_data_*.json" -type f | sort)
        if [ -n "$JSON_FILES" ]; then
            LATEST_JSON=$(echo "$JSON_FILES" | tail -n 1)
            echo "Found existing data file: $LATEST_JSON"
            
            # Extract date from filename
            LATEST_DATE=$(echo "$LATEST_JSON" | grep -o "[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}")
            if [ -f "forex_factory_events_${LATEST_DATE}.txt" ]; then
                echo "Complete events from $LATEST_DATE:"
                cat "forex_factory_events_${LATEST_DATE}.txt"
            else
                echo "Preview of data:"
                head -n 20 "$LATEST_JSON"
            fi
        fi
    fi
else
    echo "Automation failed with exit code $SCRIPT_EXIT_CODE"
    
    # Check if HTML file was created for debugging
    if [ -f "forexfactory_calendar.html" ]; then
        echo "A HTML file was saved to forexfactory_calendar.html for debugging."
        echo "You can examine this file to see what data was received from ForexFactory."
    fi
fi

echo "Done!" 