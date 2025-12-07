# POS Market Application - MVC Architecture

## Overview
This application has been refactored to follow the **Model-View-Controller (MVC)** design pattern for better maintainability, scalability, and code organization.

## Project Structure

```
POS_Market-main/
├── app.py                      # Main application entry point
├── app_old.py                  # Original monolithic application (backup)
├── requirements.txt            # Python dependencies
│
├── config/                     # Configuration module
│   ├── __init__.py
│   └── settings.py            # Application settings and paths
│
├── models/                     # Data models (M in MVC)
│   ├── __init__.py
│   ├── item.py                # Item/Product model
│   ├── trader.py              # Supplier/Trader model
│   ├── category.py            # Category model
│   ├── company.py             # Company/Manufacturer model
│   ├── sale.py                # Sales transaction model
│   ├── invoice.py             # Purchase invoice model
│   ├── user.py                # User/Authentication model
│   ├── employee.py            # Employee model
│   └── shift.py               # Work shift model
│
├── controllers/                # Business logic (C in MVC)
│   ├── __init__.py
│   ├── item_controller.py     # Item management logic
│   ├── sale_controller.py     # Sales logic
│   ├── invoice_controller.py  # Invoice logic
│   ├── shift_controller.py    # Shift management logic
│   └── report_controller.py   # Reporting logic
│
├── views/                      # Route handlers (V in MVC)
│   ├── __init__.py
│   ├── auth_views.py          # Authentication routes
│   ├── main_views.py          # Main application routes
│   ├── item_views.py          # Item management routes
│   ├── sale_views.py          # Sales routes
│   ├── invoice_views.py       # Invoice routes
│   ├── shift_views.py         # Shift management routes
│   ├── report_views.py        # Report routes
│   └── settings_views.py      # Settings & configuration routes
│
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── auth.py                # Authentication decorators
│   ├── hardware.py            # Hardware lock utilities
│   ├── logger.py              # Activity logging
│   └── printer.py             # Printing utilities
│
├── database/                   # Database layer
│   ├── __init__.py
│   ├── db.py                  # Database connection
│   ├── init_db.py             # Database initialization
│   └── schema.py              # Database schema
│
├── templates/                  # HTML templates
│   └── ...
│
└── static/                     # Static assets (CSS, JS, images)
    └── ...
```

## Architecture Pattern: MVC

### Models (models/)
- **Purpose**: Handle data and database operations
- **Responsibilities**:
  - Database queries (CRUD operations)
  - Data validation
  - Business rules related to data
- **Example**: `Item.get_all()`, `Sale.create()`

### Views (views/)
- **Purpose**: Handle HTTP requests and responses
- **Responsibilities**:
  - Route definitions using Flask Blueprints
  - Request parsing
  - Response formatting (JSON/HTML)
  - Template rendering
- **Example**: `/items`, `/save_sale`, `/get_invoice_details`

### Controllers (controllers/)
- **Purpose**: Business logic layer
- **Responsibilities**:
  - Coordinate between models and views
  - Complex business logic
  - Data transformation
  - Multi-model operations
- **Example**: `SaleController.create_sale()` handles sale creation + inventory update

## Key Features

### 1. Modular Architecture
- **Separation of Concerns**: Each layer has specific responsibilities
- **Blueprint Pattern**: Routes organized by functionality
- **Reusable Components**: Shared utilities and helpers

### 2. Configuration Management
- Centralized settings in `config/settings.py`
- Environment-specific configurations
- Easy deployment customization

### 3. Security
- Hardware lock validation
- Session management
- Permission-based access control
- Activity logging

### 4. Database Layer
- Abstracted database operations
- Connection pooling
- Transaction support

## Getting Started

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize the database:
```bash
python -c "from database.init_db import init_database; init_database()"
```

### Running the Application

```bash
python app.py
```

The application will start on `http://0.0.0.0:19523`

## Module Descriptions

### Configuration (`config/`)
- `settings.py`: Application configuration including paths, Flask settings, and hardware lock UUID

### Models (`models/`)
Each model represents a database table and provides static methods for data operations:
- `Item`: Product/inventory management
- `Sale`: Sales transactions
- `Invoice`: Purchase invoices
- `Trader`: Supplier management
- `User`: User authentication
- `Employee`: Employee management
- `Shift`: Work shift tracking
- `Category`: Product categories
- `Company`: Manufacturers/companies

### Controllers (`controllers/`)
Business logic that orchestrates models and implements complex operations:
- `ItemController`: Item CRUD + validation
- `SaleController`: Sales processing + inventory updates
- `InvoiceController`: Invoice processing + supplier balances
- `ShiftController`: Shift lifecycle management
- `ReportController`: Report generation and data aggregation

### Views (`views/`)
Flask Blueprints that define routes and handle requests:
- `auth_views`: Login/logout
- `item_views`: Item management UI and API
- `sale_views`: Sales UI and API
- `invoice_views`: Invoice UI and API
- `shift_views`: Shift management
- `report_views`: Reports and analytics
- `settings_views`: Application settings

### Utils (`utils/`)
Helper functions and decorators:
- `auth.py`: `@login_required`, `@permission_required`
- `hardware.py`: Hardware lock verification
- `logger.py`: Activity logging
- `printer.py`: Receipt and barcode printing

## Benefits of MVC Refactoring

### ✅ Maintainability
- **Before**: 9,750 lines in one file
- **After**: Organized into logical modules (~100-300 lines each)
- Easy to locate and fix bugs
- Clear responsibility for each module

### ✅ Scalability
- Add new features by creating new models/controllers/views
- No need to modify existing code
- Independent testing of components

### ✅ Collaboration
- Multiple developers can work on different modules
- Reduced merge conflicts
- Clear code ownership

### ✅ Testability
- Unit test individual models
- Integration test controllers
- Mock dependencies easily

### ✅ Reusability
- Controllers can be used by multiple views
- Models can be shared across features
- Utilities are centralized

## Development Guidelines

### Adding a New Feature

1. **Create Model** (`models/new_feature.py`)
```python
class NewFeature:
    @staticmethod
    def get_all():
        # Database query
        pass
```

2. **Create Controller** (`controllers/new_feature_controller.py`)
```python
class NewFeatureController:
    @staticmethod
    def create(data):
        # Business logic
        pass
```

3. **Create View** (`views/new_feature_views.py`)
```python
from flask import Blueprint

new_feature_bp = Blueprint('new_feature', __name__)

@new_feature_bp.route('/new_feature')
def new_feature():
    return render_template('new_feature.html')
```

4. **Register Blueprint** (in `views/__init__.py`)
```python
from .new_feature_views import new_feature_bp

all_blueprints = [
    # ... existing blueprints
    (new_feature_bp, '/'),
]
```

### Code Style
- Use descriptive variable/function names
- Add docstrings to functions
- Follow PEP 8 style guide
- Keep functions focused and single-purpose

## Migration Notes

The original `app.py` has been renamed to `app_old.py` for reference. The new architecture maintains all existing functionality while providing a cleaner structure.

### Route Changes
Some routes may have changed their blueprint prefix:
- `/login` → `auth.login`
- `/items` → `items.items`
- etc.

Most routes remain the same from the user's perspective.

## Troubleshooting

### Import Errors
Ensure you're in the project root directory when running the application.

### Database Connection Issues
Check the database configuration in `database/db.py` and ensure the database file exists.

### Missing Modules
Install all requirements: `pip install -r requirements.txt`

## Future Enhancements

- Add unit tests for models and controllers
- Implement API versioning
- Add caching layer
- Implement async operations for heavy tasks
- Add data validation schemas (e.g., marshmallow)
- Implement proper error handling middleware

## License

[Your License Here]

## Contributors

[Your Team/Name Here]
