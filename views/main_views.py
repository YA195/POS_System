"""Main application views."""
from flask import Blueprint, render_template, send_from_directory, jsonify
from utils.auth import login_required
from config.settings import STATIC_FOLDER

main_bp = Blueprint('main', __name__)


@main_bp.route('/Home')
@login_required
def home():
    """Render home page."""
    return render_template('home.html')


@main_bp.route('/barcode_generator')
@login_required
def barcode_generator():
    """Render barcode generator page."""
    return render_template('barcode_generator.html')


@main_bp.route('/inventory_audit')
@login_required
def inventory_audit():
    """Render inventory audit page."""
    return render_template('inventory_audit.html')


@main_bp.route('/previous_audits')
@login_required
def previous_audits():
    """Render previous audits page."""
    return render_template('previous_audits.html')


@main_bp.route('/cash_boxes_report')
@login_required
def cash_boxes_report():
    """Render cash boxes report page."""
    return render_template('cash_boxes_report.html')


@main_bp.route('/vendor/<path:filename>')
def vendor_files(filename):
    """Serve vendor files."""
    return send_from_directory('static/vendor', filename)


@main_bp.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files with caching."""
    cache_timeout = 31536000  # 1 year in seconds
    return send_from_directory(STATIC_FOLDER, filename, max_age=cache_timeout)


@main_bp.route('/init_db', methods=['GET', 'POST'])
def init_db_route():
    """Initialize database (if needed)."""
    try:
        # Import and run database initialization
        from database.init_db import init_database
        init_database()
        return jsonify({
            'success': True,
            'message': 'Database initialized successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Database initialization failed'
        }), 500
