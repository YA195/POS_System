TABLES = {
    # First, create tables with no foreign key dependencies
    'users': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[users]'))
    BEGIN
        CREATE TABLE users (
            id INT IDENTITY(1,1) PRIMARY KEY,
            username NVARCHAR(50) NOT NULL UNIQUE,
            password NVARCHAR(50) NOT NULL,
            permissions NVARCHAR(MAX) NOT NULL,  -- Comma-separated page names
            created_at DATETIME DEFAULT GETDATE()
        )

        -- Insert default admin user
        INSERT INTO users (username, password, permissions)
        VALUES ('admin', 'admin123', 'home,sales,items,categories,companies,reports,item_movement,settings,activity_logs,shifts,invoices,traders,delivery,closing,employees')
    END
""",
    'sections': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sections]'))
        BEGIN
            CREATE TABLE sections (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                active BIT DEFAULT 1
            )
        END
    """,
    'categories': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[categories]'))
        BEGIN
            CREATE TABLE categories (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                section_id INT,
                active BIT NOT NULL DEFAULT 1,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (section_id) REFERENCES sections(id)
            )
        END
    """,
    'cash_boxes': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[cash_boxes]'))
        BEGIN
            CREATE TABLE cash_boxes (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL UNIQUE,
                is_default BIT DEFAULT 0,
                is_active BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE()
            )
        END
    """,
    'delivery_workers': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[delivery_workers]'))
    BEGIN
        CREATE TABLE delivery_workers (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            phone NVARCHAR(20) NOT NULL,
            status NVARCHAR(20) DEFAULT 'active',
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
    END
""",
    
    'companies': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[companies]'))
        BEGIN
            CREATE TABLE companies (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(255) NULL,
                phone TEXT NOT NULL,
                active BIT NOT NULL DEFAULT 1,
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        END
    """,
    
    'shifts': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[shifts]'))
        BEGIN
            CREATE TABLE shifts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                start_time DATETIME DEFAULT GETDATE(),
                end_time DATETIME,
                cashier_name NVARCHAR(100) NOT NULL,
                sales DECIMAL(10,2) DEFAULT 0,
                invoices DECIMAL(10,2) DEFAULT 0,
                expenses DECIMAL(10,2) DEFAULT 0,
                returned_sales DECIMAL(10,2) DEFAULT 0,
                returned_items DECIMAL(10,2) DEFAULT 0,
                user_id INT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                status NVARCHAR(20) DEFAULT 'active'
            )
        END
    """,
    
    # Then tables with single-level dependencies
    'traders': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[traders]'))
        BEGIN
            CREATE TABLE traders (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(100) NOT NULL,
                phone NVARCHAR(20) NULL,
                days NVARCHAR(255) NULL,
                company_new INT NULL,
                company INT NULL,
                active BIT NOT NULL DEFAULT 1,
                created_by INT,
                CONSTRAINT FK_Traders_Companies FOREIGN KEY (company) REFERENCES companies(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        END
    """,
    
    'items': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[items]'))
        BEGIN
            CREATE TABLE items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                barcode NVARCHAR(50) UNIQUE,
                name NVARCHAR(200) NOT NULL,
                category_id INT,
                buy_price DECIMAL(10,2) NOT NULL,
                sell_price DECIMAL(10,2) NOT NULL,
                quantity INT DEFAULT 0,
                trader_id INT,
                active BIT NOT NULL DEFAULT 1,
                barcode2 NVARCHAR(500) NULL,
                created_by INT,
                updated_by INT,
                last_updated DATETIME DEFAULT GETDATE(),  -- Changed from created_at
                created_at DATETIME DEFAULT GETDATE(),    -- Keep creation date
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (trader_id) REFERENCES traders(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (updated_by) REFERENCES users(id)
            )
        END
    """,
    
'sales': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sales]'))
    BEGIN
        CREATE TABLE sales (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sale_number INT NOT NULL,
            shift_id INT NOT NULL,
            sale_date DATETIME DEFAULT GETDATE(),
            total_amount DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            discount_amount DECIMAL(10,2) DEFAULT 0,
            delivery_fee DECIMAL(10,2) DEFAULT 0,
            final_amount DECIMAL(10,2) NOT NULL,
            payment_method NVARCHAR(20) NOT NULL,
            customer_name NVARCHAR(100),
            customer_phone NVARCHAR(11),
            address_line1 NVARCHAR(255),
            address_line2 NVARCHAR(255),
            address_line3 NVARCHAR(255),
            delivery_worker_id INT,
            delivery_worker_name NVARCHAR(100),
            status NVARCHAR(20) DEFAULT 'completed',
            paid_amount DECIMAL(18,2) DEFAULT 0,
            residual_amount DECIMAL(18,2) DEFAULT 0,
            cash_box_id INT,
            user_id INT,
            created_at DATETIME DEFAULT GETDATE(),
            FOREIGN KEY (shift_id) REFERENCES shifts(id),
            FOREIGN KEY (delivery_worker_id) REFERENCES delivery_workers(id),
            FOREIGN KEY (cash_box_id) REFERENCES cash_boxes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    END
""",
    
    # Finally tables with multiple dependencies
    'sale_items': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sale_items]'))
        BEGIN
            CREATE TABLE sale_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                sale_id INT NOT NULL,
                item_id INT NOT NULL,
                barcode NVARCHAR(50) NOT NULL,
                item_name NVARCHAR(200) NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        END
    """,
    
'invoices': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[invoices]'))
    BEGIN
        CREATE TABLE invoices (
            id INT IDENTITY(1,1) PRIMARY KEY,
            invoice_date DATETIME DEFAULT GETDATE(),
            total_amount DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            discount_value DECIMAL(10,2) DEFAULT 0,
            discount_type NVARCHAR(20) DEFAULT 'fixed',
            discount_amount DECIMAL(10,2) DEFAULT 0,
            payment_type NVARCHAR(20) NOT NULL,
            paid_amount DECIMAL(10,2),
            remaining_amount DECIMAL(10,2),
            trader_id INT,
            company_id INT,
            shift_id INT,  -- Added shift_id
            user_id INT,  -- Added user_id
            status NVARCHAR(20) DEFAULT 'active',
            payment_status NVARCHAR(20) DEFAULT 'unpaid',  -- Added payment status
            FOREIGN KEY (trader_id) REFERENCES traders(id),
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (shift_id) REFERENCES shifts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    END
""",
    
    'invoice_items': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[invoice_items]'))
        BEGIN
            CREATE TABLE invoice_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                invoice_id INT NOT NULL,
                item_id INT NOT NULL,
                quantity INT NOT NULL,
                quantity_type INT NOT NULL,
                buy_price DECIMAL(10,2) NOT NULL,
                sell_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        END
    """,
    
    'invoice_payments': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[invoice_payments]'))
        BEGIN
            CREATE TABLE invoice_payments (
                id INT IDENTITY(1,1) PRIMARY KEY,
                invoice_id INT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                payment_date DATETIME DEFAULT GETDATE(),
                notes NVARCHAR(255),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        END
    """,
    
    'item_price_history': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[item_price_history]'))
        BEGIN
            CREATE TABLE item_price_history (
                id INT IDENTITY(1,1) PRIMARY KEY,
                item_id INT NOT NULL,
                old_buy_price DECIMAL(10,2) NOT NULL,
                new_buy_price DECIMAL(10,2) NOT NULL,
                old_sell_price DECIMAL(10,2) NOT NULL,
                new_sell_price DECIMAL(10,2) NOT NULL,
                change_date DATETIME DEFAULT GETDATE(),
                invoice_id INT,
                FOREIGN KEY (item_id) REFERENCES items(id),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        END
    """,
    
    'sale_returns': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sale_returns]'))
        BEGIN
            CREATE TABLE sale_returns (
                id INT IDENTITY(1,1) PRIMARY KEY,
                sale_id INT NOT NULL,
                return_date DATETIME DEFAULT GETDATE(),
                total_amount DECIMAL(10,2) NOT NULL,
                reason NVARCHAR(255),
                user_id INT,
                status NVARCHAR(20) DEFAULT 'completed',
                FOREIGN KEY (sale_id) REFERENCES sales(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        END
    """,
    
    'return_items': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[return_items]'))
        BEGIN
            CREATE TABLE return_items (
                id INT IDENTITY(1,1) PRIMARY KEY,
                return_id INT NOT NULL,
                item_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (return_id) REFERENCES sale_returns(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        END
    """,
    'settings': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[settings]'))
    BEGIN
        CREATE TABLE settings (
            id INT IDENTITY(1,1) PRIMARY KEY,
            store_name NVARCHAR(100) NOT NULL,
            store_phone NVARCHAR(20) NULL,
            store_address NVARCHAR(255) NULL,
            receipt_footer NVARCHAR(255) NULL,
            printer_name NVARCHAR(100) NULL,
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
    END
""",
'expenses': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[expenses]'))
    BEGIN
        CREATE TABLE expenses (
            id INT IDENTITY(1,1) PRIMARY KEY,
            shift_id INT NOT NULL,
            shift_date DATETIME NULL,
            amount DECIMAL(10,2) NOT NULL,
            description NVARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT GETDATE(),
            user_id INT,
            FOREIGN KEY (shift_id) REFERENCES shifts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    END
""",
    'customers': """
        IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[customers]'))
        BEGIN
            CREATE TABLE customers (
                id INT IDENTITY(1,1) PRIMARY KEY,
                phone_number NVARCHAR(20) NOT NULL UNIQUE,
                name NVARCHAR(100) NOT NULL,
                address_line1 NVARCHAR(255),
                address_line2 NVARCHAR(255),
                address_line3 NVARCHAR(255),
                lastorder DATETIME NULL,
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
        END
    """,
    # Add to TABLES dictionary


# Add these new tables to your TABLES dictionary

'daily_sales': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[daily_sales]'))
    BEGIN
        CREATE TABLE daily_sales (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sale_number INT NOT NULL,
            shift_id INT NOT NULL,
            sale_date DATETIME DEFAULT GETDATE(),
            total_amount DECIMAL(10,2) NOT NULL,
            subtotal DECIMAL(10,2) NOT NULL,
            discount_amount DECIMAL(10,2) DEFAULT 0,
            delivery_fee DECIMAL(10,2) DEFAULT 0,
            final_amount DECIMAL(10,2) NOT NULL,
            payment_method NVARCHAR(20) NOT NULL,
            customer_name NVARCHAR(100),
            customer_phone NVARCHAR(11),
            address_line1 NVARCHAR(255),
            address_line2 NVARCHAR(255),
            address_line3 NVARCHAR(255),
            delivery_worker_id INT,
            delivery_worker_name NVARCHAR(100),
            status NVARCHAR(20) DEFAULT 'completed',
            paid_amount DECIMAL(18,2) DEFAULT 0,
            residual_amount DECIMAL(18,2) DEFAULT 0,
            cash_box_id INT,
            user_id INT,
            created_at DATETIME DEFAULT GETDATE(),
            FOREIGN KEY (shift_id) REFERENCES shifts(id),
            FOREIGN KEY (delivery_worker_id) REFERENCES delivery_workers(id),
            FOREIGN KEY (cash_box_id) REFERENCES cash_boxes(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    END
""",

'daily_sale_items': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[daily_sale_items]'))
    BEGIN
        CREATE TABLE daily_sale_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sale_id INT NOT NULL,
            item_id INT NOT NULL,
            barcode NVARCHAR(50) NOT NULL,
            item_name NVARCHAR(200) NOT NULL,
            quantity DECIMAL(10,2) NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES daily_sales(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )
    END
""",
'daily_sale_returns': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[daily_sale_returns]'))
    BEGIN
        CREATE TABLE daily_sale_returns (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sale_id INT NOT NULL,
            return_date DATETIME DEFAULT GETDATE(),
            total_amount DECIMAL(10,2) NOT NULL,
            reason NVARCHAR(255),
            status NVARCHAR(20) DEFAULT 'completed',
            shift_id INT NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES daily_sales(id),
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
    END
""",

'daily_return_items': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[daily_return_items]'))
    BEGIN
        CREATE TABLE daily_return_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            return_id INT NOT NULL,
            item_id INT NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            total_price DECIMAL(10,2) NOT NULL,
            user_id INT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (return_id) REFERENCES daily_sale_returns(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )
    END
""",

    'inventory_audits': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[inventory_audits]'))
    BEGIN
        CREATE TABLE inventory_audits (
            id INT IDENTITY(1,1) PRIMARY KEY,
            audit_date DATETIME DEFAULT GETDATE(),
            user_id INT,
            status NVARCHAR(20) DEFAULT 'saved',
            approved BIT DEFAULT 0
        )
    END
""",

    'inventory_audit_items': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[inventory_audit_items]'))
    BEGIN
        CREATE TABLE inventory_audit_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            audit_id INT NOT NULL,
            item_id INT NOT NULL,
            expected_quantity INT NOT NULL,
            barcode NVARCHAR(50),
            name NVARCHAR(200),
            previous_quantity INT NOT NULL,
            actual_quantity INT NOT NULL,
            shortage INT DEFAULT 0,
            excess INT DEFAULT 0,
            FOREIGN KEY (audit_id) REFERENCES inventory_audits(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )
    END
""",

    'shift_cash_boxes': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[shift_cash_boxes]'))
    BEGIN
        CREATE TABLE shift_cash_boxes (
            id INT IDENTITY(1,1) PRIMARY KEY,
            shift_id INT NOT NULL,
            cash_box_id INT NOT NULL,
            amount DECIMAL(10,2) DEFAULT 0,
            FOREIGN KEY (shift_id) REFERENCES shifts(id),
            FOREIGN KEY (cash_box_id) REFERENCES cash_boxes(id)
        )
    END
""",

    'cash_box_transfers': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[cash_box_transfers]'))
    BEGIN
        CREATE TABLE cash_box_transfers (
            id INT IDENTITY(1,1) PRIMARY KEY,
            from_cash_box_id INT NULL,  -- NULL for deposits (money coming from outside)
            to_cash_box_id INT NULL,    -- NULL for withdrawals (money going outside)
            amount DECIMAL(10,2) NOT NULL,
            shift_id INT,
            transfer_date DATETIME DEFAULT GETDATE(),
            notes NVARCHAR(500),
            user_id INT,
            FOREIGN KEY (from_cash_box_id) REFERENCES cash_boxes(id),
            FOREIGN KEY (to_cash_box_id) REFERENCES cash_boxes(id),
            FOREIGN KEY (shift_id) REFERENCES shifts(id)
        )
    END
""",

    'activity_logs': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[activity_logs]'))
    BEGIN
        CREATE TABLE activity_logs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL,
            username NVARCHAR(50),
            action_type NVARCHAR(50) NOT NULL,
            table_name NVARCHAR(50),
            record_id INT,
            description NVARCHAR(500),
            ip_address NVARCHAR(50),
            created_at DATETIME DEFAULT GETDATE(),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        
        -- Create indexes for better performance
        CREATE INDEX IX_activity_logs_user_id ON activity_logs(user_id);
        CREATE INDEX IX_activity_logs_created_at ON activity_logs(created_at DESC);
        CREATE INDEX IX_activity_logs_action_type ON activity_logs(action_type);
    END
""",

    'employees': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[employees]'))
    BEGIN
        CREATE TABLE employees (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100) NOT NULL,
            phone NVARCHAR(20),
            job_title NVARCHAR(100),
            is_active BIT DEFAULT 1,
            created_at DATETIME DEFAULT GETDATE(),
            updated_at DATETIME DEFAULT GETDATE()
        )
    END
""",

    'employee_disbursements': """
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[employee_disbursements]'))
    BEGIN
        CREATE TABLE employee_disbursements (
            id INT IDENTITY(1,1) PRIMARY KEY,
            employee_id INT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            disbursement_date DATETIME DEFAULT GETDATE(),
            notes NVARCHAR(500),
            cash_box_id INT,
            given_by_user_id INT NOT NULL,
            given_by_username NVARCHAR(50),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (cash_box_id) REFERENCES cash_boxes(id),
            FOREIGN KEY (given_by_user_id) REFERENCES users(id)
        )
    END
""",
}
