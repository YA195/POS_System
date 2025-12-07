"""Hardware lock utilities for application security."""
import sys
import subprocess
from config.settings import AUTHORIZED_UUID


def check_hardware_lock():
    """Check if the application is running on authorized hardware"""
    try:
        # Get the Raw Output
        result = subprocess.check_output(
            'wmic csproduct get uuid', 
            shell=True
        ).decode()
        
        # Aggressive Cleaning
        # Remove the word "UUID" if it's there
        machine_uuid = result.replace("UUID", "")
        # Remove ALL whitespace (newlines \n, returns \r, spaces, tabs)
        machine_uuid = "".join(machine_uuid.split())
        
        # Compare
        if machine_uuid != AUTHORIZED_UUID:
            print("!!! HARDWARE MISMATCH !!!")
            print(f"Found:    [{machine_uuid}]")
            sys.exit(1)
            
    except Exception as e:
        print(f"Hardware check error: {e}")
        sys.exit(1)
