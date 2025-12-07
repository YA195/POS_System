"""Application configuration settings."""
import sys
import os
from datetime import timedelta


def get_base_path():
    """Get the base path for the application (works for both script and frozen exe)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for Nuitka compiled"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - resources are embedded
        base_path = os.path.dirname(sys.argv[0])
        return os.path.join(base_path, relative_path)
    else:
        # Running as script
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)


# Path configuration
BASE_PATH = get_base_path()
TEMPLATE_FOLDER = get_resource_path('templates')
STATIC_FOLDER = get_resource_path('static')
CONFIG_PATH = r'C:\Program Files\ELmohandes\config.txt'

# Flask configuration
SECRET_KEY = 'dev_secret_key_123456789'  # Change in production!
SESSION_TYPE = 'flask_session'
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

# Application configuration
HOST = '0.0.0.0'
PORT = 19523
DEBUG = True

# Hardware Lock Configuration
AUTHORIZED_UUID = "4C4C4544-0059-3510-8037-B2C04F4A5033"
