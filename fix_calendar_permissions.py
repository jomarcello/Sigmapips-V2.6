#!/usr/bin/env python3
import os
import sys
import subprocess
import stat

def main():
    # Locate the get_today_events.py script
    base_path = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_path, "get_today_events.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Script not found at {script_path}")
        return
    
    print(f"Found script at {script_path}")
    
    # Check if the script has the proper shebang line
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Add a shebang line if it doesn't have one
    if not content.startswith("#!/usr/bin/env python"):
        print("Adding proper shebang line to the script...")
        with open(script_path, 'w') as f:
            f.write("#!/usr/bin/env python3\n" + content)
        print("✅ Added shebang line")
    else:
        print("✅ Script already has a proper shebang line")
    
    # Make the script executable
    try:
        current_mode = os.stat(script_path).st_mode
        os.chmod(script_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("✅ Made script executable")
    except Exception as e:
        print(f"❌ Error making script executable: {str(e)}")
    
    # Test if the script can be run directly
    print("\nTesting direct script execution...")
    try:
        result = subprocess.run([script_path], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Direct script execution successful")
            if result.stdout:
                print(f"Script output (first 100 chars): {result.stdout[:100]}...")
        else:
            print(f"❌ Direct script execution failed with exit code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")
    except Exception as e:
        print(f"❌ Error testing script: {str(e)}")
    
    # Check forex_factory_data_*.json files
    print("\nChecking for existing ForexFactory data files:")
    data_files = [f for f in os.listdir(base_path) if f.startswith("forex_factory_data_") and f.endswith(".json")]
    
    if data_files:
        print(f"Found {len(data_files)} data files:")
        for file in data_files:
            try:
                file_path = os.path.join(base_path, file)
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)
                print(f"  - {file} ({size} bytes)")
            except Exception as e:
                print(f"  - {file} (error: {str(e)})")
    else:
        print("No existing data files found")
    
    print("\nCalendar script fixup complete!")

if __name__ == "__main__":
    main() 