PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    bottle_size_oz REAL NOT NULL CHECK (bottle_size_oz > 0),
    cost REAL NOT NULL CHECK (cost >= 0),
    empty_bottle_weight REAL NOT NULL CHECK (empty_bottle_weight >= 0),
    full_bottle_weight REAL NOT NULL CHECK (full_bottle_weight > empty_bottle_weight),
    pour_spout_weight REAL,
    uses_standard_weighing INTEGER NOT NULL DEFAULT 1,
    low_stock_threshold_oz REAL NOT NULL DEFAULT 0 CHECK (low_stock_threshold_oz >= 0),
    low_stock_threshold_unopened INTEGER NOT NULL DEFAULT 0 CHECK (low_stock_threshold_unopened >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, category_id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS daily_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_date TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    unopened_bottle_count INTEGER NOT NULL DEFAULT 0 CHECK (unopened_bottle_count >= 0),
    total_opened_ounces_remaining REAL NOT NULL DEFAULT 0 CHECK (total_opened_ounces_remaining >= 0),
    total_stock_on_hand_oz REAL NOT NULL DEFAULT 0 CHECK (total_stock_on_hand_oz >= 0),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (inventory_date, product_id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS open_bottle_weighins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    daily_inventory_id INTEGER NOT NULL,
    inventory_date TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    bottle_identifier TEXT,
    measured_bottle_weight REAL NOT NULL CHECK (measured_bottle_weight >= 0),
    estimated_ounces_remaining REAL NOT NULL CHECK (estimated_ounces_remaining >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (daily_inventory_id) REFERENCES daily_inventory(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS restock_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_date TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    quantity_received INTEGER NOT NULL CHECK (quantity_received > 0),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_daily_inventory_date ON daily_inventory(inventory_date);
CREATE INDEX IF NOT EXISTS idx_daily_inventory_product_id ON daily_inventory(product_id);
CREATE INDEX IF NOT EXISTS idx_weighins_inventory_date ON open_bottle_weighins(inventory_date);
CREATE INDEX IF NOT EXISTS idx_restock_delivery_date ON restock_deliveries(delivery_date);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    inventory_date TEXT,
    product_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
