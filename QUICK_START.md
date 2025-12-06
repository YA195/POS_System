# Quick Start Guide - MVC POS Market

## 🚀 Getting Started in 5 Minutes

### 1. Installation
```bash
cd d:\POS_Market-main\POS_Market-main
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Access the Application
Open your browser and go to: `http://localhost:19523`

---

## 📁 Quick File Reference

Need to modify something? Here's where to look:

| What You Need | Where to Look |
|---------------|---------------|
| **Add/modify routes** | `views/` folder |
| **Database queries** | `models/` folder |
| **Business logic** | `controllers/` folder |
| **Configuration** | `config/settings.py` |
| **Authentication** | `utils/auth.py` |
| **Printing** | `utils/printer.py` |

---

## 🔧 Common Modifications

### Change Server Port
**File**: `config/settings.py`
```python
PORT = 19523  # Change this number
```

### Add New Permission
**File**: `utils/auth.py`
```python
@permission_required('new_permission')
def my_route():
    pass
```

### Modify Database Connection
**File**: `database/db.py`

---

## 📋 Project Structure (Simplified)

```
POS_Market-main/
├── app.py              ← Start here
├── config/             ← Settings
├── models/             ← Database
├── controllers/        ← Logic
├── views/              ← Routes
├── utils/              ← Helpers
├── templates/          ← HTML
└── static/             ← CSS/JS
```

---

## 🎯 Development Workflow

### Adding a New Feature (Example: "Products")

**Step 1**: Create Model (`models/product.py`)
```python
class Product:
    @staticmethod
    def get_all():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        return cursor.fetchall()
```

**Step 2**: Create Controller (`controllers/product_controller.py`)
```python
class ProductController:
    @staticmethod
    def get_products():
        return Product.get_all()
```

**Step 3**: Create View (`views/product_views.py`)
```python
from flask import Blueprint, jsonify

product_bp = Blueprint('products', __name__)

@product_bp.route('/products')
def products():
    items = ProductController.get_products()
    return jsonify({'items': items})
```

**Step 4**: Register Blueprint (`views/__init__.py`)
```python
from .product_views import product_bp

all_blueprints = [
    # ... existing
    (product_bp, '/'),
]
```

---

## 🐛 Troubleshooting

### Application Won't Start

**Error**: `ModuleNotFoundError`
```bash
# Make sure you're in the right directory
cd d:\POS_Market-main\POS_Market-main
python app.py
```

**Error**: `Hardware mismatch`
```python
# Comment out in app.py temporarily
# check_hardware_lock()
```

### Route Not Found (404)

Check the route is registered:
```bash
# Look at startup output for registered routes
python app.py
# You'll see all routes listed
```

### Database Error

Reinitialize database:
```python
python -c "from database.init_db import init_database; init_database()"
```

---

## 📖 Documentation Files

- **README_MVC.md** - Complete architecture documentation
- **ARCHITECTURE.md** - Visual diagrams and flow charts
- **MIGRATION_GUIDE.md** - Moving from old to new structure
- **QUICK_START.md** - This file

---

## 🔍 Finding Code Examples

### Need to see how to...

**Create a new item?**
→ Look at `controllers/item_controller.py` → `create_item()`

**Process a sale?**
→ Look at `controllers/sale_controller.py` → `create_sale()`

**Generate a report?**
→ Look at `controllers/report_controller.py`

**Add authentication?**
→ Look at `utils/auth.py` → `@login_required`

---

## 💡 Pro Tips

1. **Use blueprints** for organizing routes by feature
2. **Keep models simple** - just database operations
3. **Put business logic in controllers** - validation, calculations, etc.
4. **Use descriptive names** - `create_sale()` not `cs()`
5. **Log important actions** - use `log_activity()`

---

## 🎨 Code Style

### Naming Conventions
- **Files**: `snake_case.py` (e.g., `item_controller.py`)
- **Classes**: `PascalCase` (e.g., `ItemController`)
- **Functions**: `snake_case` (e.g., `get_all_items()`)
- **Variables**: `snake_case` (e.g., `item_id`)
- **Blueprints**: `name_bp` (e.g., `item_bp`)

---

## 🧪 Testing Your Changes

### Manual Testing Checklist
```
□ Start the application
□ Login successfully
□ Test your new feature
□ Check database updates
□ Check console for errors
□ Test with different users/permissions
```

---

## 📞 Help & Support

### Understanding the Flow
```
User Request
    ↓
View (routes)
    ↓
Controller (business logic)
    ↓
Model (database)
    ↓
Response
```

### Common Patterns

**Pattern 1: Simple Data Retrieval**
```python
# View
@bp.route('/items')
def items():
    items = Item.get_all()  # Direct model call
    return jsonify(items)
```

**Pattern 2: Complex Operation**
```python
# View
@bp.route('/save_sale')
def save_sale():
    data = request.get_json()
    sale_id = SaleController.create_sale(data)  # Use controller
    return jsonify({'sale_id': sale_id})
```

---

## ⚡ Performance Tips

1. **Database**: Use indexes on frequently queried columns
2. **Queries**: Fetch only needed columns
3. **Caching**: Static files are cached (31536000 seconds)
4. **Sessions**: Expire after 12 hours (configurable)

---

## 🔒 Security Notes

- Hardware lock enabled (can be disabled in config)
- Session validation on each request
- Permission-based access control
- Activity logging for auditing

---

## 📦 Dependencies

All in `requirements.txt`:
- Flask - Web framework
- pyodbc - Database connectivity
- pywin32 - Windows printing
- python-barcode - Barcode generation
- Pillow - Image processing

---

## 🚦 Status Indicators

When running the app, you'll see:
```
Starting POS Market Application on 0.0.0.0:19523
Debug mode: True
Template folder: d:\...\templates
Static folder: d:\...\static

=== Registered Routes ===
auth.login                               /login
items.items                             /items
...
```

Green checkmarks ✅ mean everything loaded successfully!

---

## 🎓 Learning Path

1. **Day 1**: Understand the structure (read README_MVC.md)
2. **Day 2**: Make a small change (add a route)
3. **Day 3**: Add a new feature (following the workflow)
4. **Day 4**: Optimize existing code
5. **Day 5**: Share knowledge with team

---

## ✅ Checklist for New Developers

- [ ] Installed all dependencies
- [ ] Can run the application
- [ ] Read README_MVC.md
- [ ] Understand MVC pattern
- [ ] Know where to find routes (views/)
- [ ] Know where to find business logic (controllers/)
- [ ] Know where to find database code (models/)
- [ ] Made a test change
- [ ] Familiar with git workflow

---

## 🎉 You're Ready!

The codebase is now organized, maintainable, and follows industry best practices. 

**Happy coding! 🚀**

---

*For detailed information, see README_MVC.md and ARCHITECTURE.md*
