# Migration Guide - From Monolithic to MVC

## Overview
This guide helps you understand the changes and how to work with the new MVC structure.

## What Changed?

### File Structure
- **Before**: Everything in `app.py` (9,750 lines)
- **After**: Organized into MVC folders with ~40 files

### Route Names
Some routes now use blueprint prefixes. Here's the mapping:

| Old Route | New Blueprint Route | File Location |
|-----------|-------------------|---------------|
| `/login` | `auth.login` | `views/auth_views.py` |
| `/logout` | `auth.logout` | `views/auth_views.py` |
| `/Home` | `main.home` | `views/main_views.py` |
| `/items` | `items.items` | `views/item_views.py` |
| `/save_item` | `items.save_item` | `views/item_views.py` |
| `/sales` | `sales.sales` | `views/sale_views.py` |
| `/save_sale` | `sales.save_sale` | `views/sale_views.py` |
| `/invoice` | `invoices.invoice` | `views/invoice_views.py` |
| `/shifts` | `shifts.shifts` | `views/shift_views.py` |
| `/reports` | `reports.reports` | `views/report_views.py` |
| `/settings` | `settings.settings` | `views/settings_views.py` |

## Finding Your Code

### "Where is the login function?"
**Before**: Line ~230 in `app.py`
**After**: `views/auth_views.py` → `login()` function

### "Where is the save_sale function?"
**Before**: Line ~2221 in `app.py`
**After**: `views/sale_views.py` → `save_sale()` function

### "Where is the item database query?"
**Before**: Inline SQL in route handlers in `app.py`
**After**: `models/item.py` → `Item` class methods

### "Where is the business logic for sales?"
**Before**: Mixed with routes in `app.py`
**After**: `controllers/sale_controller.py` → `SaleController` class

## Common Tasks

### 1. Adding a New Route

**Before (in app.py):**
```python
@app.route('/my_route')
@login_required
def my_route():
    # All logic here
    pass
```

**After (in appropriate views file):**
```python
# In views/item_views.py (or create new blueprint file)
@item_bp.route('/my_route')
@login_required
def my_route():
    # Call controller
    data = ItemController.get_data()
    return jsonify({'success': True, 'data': data})
```

### 2. Adding Database Query

**Before (in app.py):**
```python
@app.route('/get_items')
def get_items():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    return jsonify({'items': items})
```

**After:**

**Model** (`models/item.py`):
```python
class Item:
    @staticmethod
    def get_all():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items")
        return cursor.fetchall()
```

**View** (`views/item_views.py`):
```python
@item_bp.route('/get_items')
def get_items():
    items = Item.get_all()
    return jsonify({'items': items})
```

### 3. Adding Business Logic

**After (recommended):**

**Controller** (`controllers/item_controller.py`):
```python
class ItemController:
    @staticmethod
    def create_item(data):
        # Validation
        if not data.get('barcode'):
            raise ValueError("Barcode is required")
        
        # Check duplicates
        existing = Item.get_by_barcode(data['barcode'])
        if existing:
            raise ValueError("Barcode already exists")
        
        # Create item
        item_id = Item.create(data)
        
        # Log activity
        log_activity('CREATE', f"Created item: {data['item_name']}")
        
        return item_id
```

**View** (`views/item_views.py`):
```python
@item_bp.route('/save_item', methods=['POST'])
def save_item():
    try:
        data = request.get_json()
        item_id = ItemController.create_item(data)
        return jsonify({'success': True, 'item_id': item_id})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
```

## Updating Existing Code

### If you need to modify a route:

1. **Find the route** using search: `Ctrl+Shift+F` and search for the route path
2. **Locate the blueprint file** (e.g., `views/item_views.py`)
3. **Modify the function**
4. If you need database operations, use/update the corresponding model
5. If you need business logic, use/update the corresponding controller

### Example: Modifying the save_sale route

1. Search for `'/save_sale'` → Found in `views/sale_views.py`
2. Open `views/sale_views.py`
3. Function: `save_sale()`
4. It calls: `SaleController.create_sale()`
5. To modify logic: Edit `controllers/sale_controller.py`
6. To modify database: Edit `models/sale.py`

## URL Generation

### In Templates

**Before:**
```html
<a href="{{ url_for('login') }}">Login</a>
<a href="{{ url_for('items') }}">Items</a>
```

**After:**
```html
<a href="{{ url_for('auth.login') }}">Login</a>
<a href="{{ url_for('items.items') }}">Items</a>
```

### In Python Code

**Before:**
```python
return redirect(url_for('login'))
```

**After:**
```python
return redirect(url_for('auth.login'))
```

## Debugging

### Finding Errors

If you get an error like: `werkzeug.routing.BuildError: Could not build url for endpoint 'items'`

**Solution**: Use the blueprint prefix: `'items.items'` instead of `'items'`

### Import Errors

If you get: `ModuleNotFoundError: No module named 'models'`

**Solution**: Make sure you're running from the project root directory where `app.py` is located.

### Route Not Found

If a route returns 404:

1. Check registered routes: The app prints all routes on startup
2. Verify blueprint is registered in `views/__init__.py`
3. Check route path spelling

## Configuration Changes

### Before
```python
# In app.py
app.secret_key = 'dev_secret_key_123456789'
CONFIG_PATH = r'C:\Program Files\ELmohandes\config.txt'
```

### After
```python
# In config/settings.py
SECRET_KEY = 'dev_secret_key_123456789'
CONFIG_PATH = r'C:\Program Files\ELmohandes\config.txt'
```

To change config: Edit `config/settings.py`

## Testing the Migration

### 1. Check All Routes Work
Run the app and verify:
```bash
python app.py
```

Look for the route list printed on startup.

### 2. Test Each Feature
- [ ] Login/Logout
- [ ] Create/Edit/Delete Items
- [ ] Create Sales
- [ ] Create Invoices
- [ ] View Reports
- [ ] Manage Shifts
- [ ] Settings

### 3. Check Database
Verify data is being saved correctly:
- Create a test item
- Make a test sale
- Check the database tables

## Rollback Plan

If something breaks, you can temporarily rollback:

1. Rename current `app.py` to `app_new.py`
2. Rename `app_old.py` to `app.py`
3. Run: `python app.py`

This gives you time to fix issues in the new code.

## Performance Considerations

The new structure has minimal performance impact:
- ✅ No additional database queries
- ✅ No significant memory overhead
- ✅ Import cost is negligible (happens once at startup)

## FAQ

### Q: Do I need to update the database?
**A:** No, the database schema remains the same.

### Q: Will the old app.py still work?
**A:** Yes, it's saved as `app_old.py` if you need it.

### Q: Can I mix old and new code?
**A:** Not recommended. Stick with the new MVC structure.

### Q: How do I add a completely new feature?
**A:** 
1. Create model in `models/`
2. Create controller in `controllers/`
3. Create view blueprint in `views/`
4. Register blueprint in `views/__init__.py`

### Q: Where do I put utility functions?
**A:** In `utils/` directory. Create a new file if needed.

### Q: Can I still use `@app.route`?
**A:** Yes, but use blueprints instead: `@blueprint_name.route()`

## Getting Help

If you're stuck:
1. Check `README_MVC.md` for architecture overview
2. Check `ARCHITECTURE.md` for diagrams
3. Look at existing views/controllers/models as examples
4. Search for similar functionality in the codebase

## Next Steps

1. Familiarize yourself with the new structure
2. Read the README_MVC.md file
3. Try making a small change to understand the flow
4. Update any custom code you've added to follow MVC pattern

## Benefits Recap

✅ **Easier to find code**: Organized by feature
✅ **Easier to test**: Isolated components
✅ **Easier to modify**: Changes don't affect other parts
✅ **Easier to collaborate**: Multiple developers can work simultaneously
✅ **Better performance**: More efficient imports and loading
✅ **Industry standard**: Follows best practices
