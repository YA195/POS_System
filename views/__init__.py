"""Views package containing route blueprints."""
from .auth_views import auth_bp
from .item_views import item_bp
from .sale_views import sale_bp
from .invoice_views import invoice_bp
from .shift_views import shift_bp
from .report_views import report_bp
from .main_views import main_bp
from .settings_views import settings_bp

# List of all blueprints to register
all_blueprints = [
    (auth_bp, '/'),
    (main_bp, '/'),
    (item_bp, '/'),
    (sale_bp, '/'),
    (invoice_bp, '/'),
    (shift_bp, '/'),
    (report_bp, '/'),
    (settings_bp, '/'),
]
