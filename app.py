"""
POS Market Application - Main Entry Point
Refactored to follow MVC (Model-View-Controller) pattern
"""
import sys
from flask import Flask, g
from datetime import timedelta

# Import configuration
from config import (
    SECRET_KEY, SESSION_TYPE, SESSION_PERMANENT,
    PERMANENT_SESSION_LIFETIME, TEMPLATE_FOLDER, STATIC_FOLDER,
    HOST, PORT, DEBUG
)

# Import utilities
from utils.hardware import check_hardware_lock
from utils.auth import check_session

# Import database initialization
from database.db import init_app

# Import all blueprints
from views import all_blueprints


def create_app():
    """Application factory pattern."""
    
    # Check hardware lock before starting
    check_hardware_lock()
    
    # Initialize Flask app
    app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
    
    # Configure Flask
    app.secret_key = SECRET_KEY
    app.permanent_session_lifetime = PERMANENT_SESSION_LIFETIME
    app.config['SESSION_TYPE'] = SESSION_TYPE
    app.config['SESSION_PERMANENT'] = SESSION_PERMANENT
    app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
    
    # Initialize database
    init_app(app)
    
    # Register blueprints
    for blueprint, url_prefix in all_blueprints:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
    
    # Add cache control headers
    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    # Session validation before each request
    @app.before_request
    def before_request():
        return check_session()
    
    return app


def main():
    """Main entry point."""
    app = create_app()
    
    # Print registered routes for debugging
    if DEBUG:
        print("\n=== Registered Routes ===")
        for rule in app.url_map.iter_rules():
            print(f"{rule.endpoint:40s} {rule.rule}")
        print("=" * 60 + "\n")
    
    # Run the application
    print(f"Starting POS Market Application on {HOST}:{PORT}")
    print(f"Debug mode: {DEBUG}")
    print(f"Template folder: {TEMPLATE_FOLDER}")
    print(f"Static folder: {STATIC_FOLDER}\n")
    
    app.run(host=HOST, port=PORT, debug=DEBUG)


if __name__ == '__main__':
    main()
