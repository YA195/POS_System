# POS Market - MVC Architecture Diagram

## Request Flow

```
┌─────────────┐
│   Browser   │
│  (Client)   │
└──────┬──────┘
       │
       │ HTTP Request
       ▼
┌─────────────────────────────────────────────────────────┐
│                      Flask App                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Middleware Layer                                 │  │
│  │  • Session validation (@before_request)           │  │
│  │  • Cache headers (@after_request)                 │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   VIEWS (Blueprints)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Auth      │  │   Items     │  │   Sales     │     │
│  │   Views     │  │   Views     │  │   Views     │ ... │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  • Parse request                                        │
│  • Call controller                                      │
│  • Format response                                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   CONTROLLERS                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │    Item     │  │    Sale     │  │  Invoice    │     │
│  │ Controller  │  │ Controller  │  │ Controller  │ ... │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  • Business logic                                       │
│  • Validation                                           │
│  • Coordinate models                                    │
│  • Activity logging                                     │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                      MODELS                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │    Item     │  │    Sale     │  │  Invoice    │     │
│  │   Model     │  │   Model     │  │   Model     │ ... │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  • CRUD operations                                      │
│  • Database queries                                     │
│  • Data access logic                                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   DATABASE LAYER                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │          SQL Server / SQLite Database            │   │
│  │  • Items  • Sales  • Invoices  • Users  ...     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Module Relationships

```
┌──────────────────────────────────────────────────────────────┐
│                        app.py                                │
│  • Application factory                                       │
│  • Blueprint registration                                    │
│  • Middleware setup                                          │
└────────────┬─────────────────────────────────┬───────────────┘
             │                                 │
     ┌───────▼────────┐                ┌──────▼──────┐
     │   config/      │                │   utils/    │
     │  settings.py   │                │  • auth     │
     └───────┬────────┘                │  • logger   │
             │                         │  • printer  │
             │                         └──────┬──────┘
             │                                │
        ┌────▼──────────────────────┬─────────▼─────┐
        │                           │                │
  ┌─────▼─────┐            ┌────────▼──────┐  ┌─────▼──────┐
  │  views/   │            │ controllers/  │  │  models/   │
  │           │───────────▶│               │─▶│            │
  │ Blueprints│            │ Business      │  │ Data       │
  │           │            │ Logic         │  │ Access     │
  └───────────┘            └───────────────┘  └─────┬──────┘
                                                     │
                                              ┌──────▼──────┐
                                              │ database/   │
                                              │   db.py     │
                                              └─────────────┘
```

## Example: Create Sale Flow

```
1. User submits sale form
   │
   ▼
2. POST /save_sale → sale_views.save_sale()
   │
   ├─ Parse JSON request data
   └─ Call SaleController.create_sale()
      │
      ▼
3. SaleController.create_sale()
   │
   ├─ Validate items (check inventory)
   ├─ Call Sale.create(sale_data, items)
   │  │
   │  └─ Insert into daily_sales table
   │     Insert into daily_sale_items table
   │
   ├─ Update inventory (Item model)
   │  │
   │  └─ UPDATE items SET quantity = quantity - ?
   │
   └─ Log activity (log_activity())
      │
      └─ INSERT INTO activity_logs
      
4. Return JSON response
   │
   └─ { success: true, sale_id: 123 }
```

## File Organization by Feature

```
Item Management Feature:
├── models/item.py           ← Data operations
├── controllers/item_controller.py  ← Business logic
├── views/item_views.py      ← Routes
└── templates/Items.html     ← UI

Sale Feature:
├── models/sale.py
├── controllers/sale_controller.py
├── views/sale_views.py
└── templates/sales.html

Invoice Feature:
├── models/invoice.py
├── controllers/invoice_controller.py
├── views/invoice_views.py
└── templates/invoice.html
```

## Benefits Summary

### Before (Monolithic)
```
app.py (9,750 lines)
├── All routes
├── All business logic
├── All database queries
├── All utilities
└── Hard to maintain
```

### After (MVC)
```
app.py (85 lines)
├── config/        (50 lines)
├── models/        (~800 lines across 9 files)
├── controllers/   (~600 lines across 5 files)
├── views/         (~1000 lines across 8 files)
└── utils/         (~300 lines across 4 files)

Total: ~2,835 lines (organized)
```

## Key Principles

1. **Separation of Concerns**: Each layer has one responsibility
2. **DRY (Don't Repeat Yourself)**: Reusable components
3. **Single Responsibility**: Each class/function does one thing
4. **Dependency Injection**: Views depend on controllers, controllers depend on models
5. **Loose Coupling**: Changes in one layer don't break others
