import sqlite3
from pathlib import Path
from flask import g

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "inventory.db"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    schema_path = BASE_DIR / "schema.sql"
    with app.app_context():
        db = get_db()
        db.executescript(schema_path.read_text(encoding="utf-8"))
        db.commit()


def seed_db(app):
    sample_categories = ["Whiskey", "Vodka", "Tequila", "Rum", "Gin", "Liqueur"]

    sample_products = [
        ("Jack Daniel's", "Whiskey", 25.36, 21.0, 18.0, 43.0, None, 1, 20.0, 1, 1),
        ("Crown Royal", "Whiskey", 25.36, 28.0, 19.0, 44.0, None, 1, 20.0, 1, 1),
        ("Tito's", "Vodka", 25.36, 24.0, 17.5, 42.5, None, 1, 20.0, 1, 1),
        ("Patrón Silver", "Tequila", 25.36, 34.0, 21.0, 46.0, None, 1, 18.0, 1, 1),
        ("Bacardi Superior", "Rum", 25.36, 19.0, 17.0, 41.5, None, 1, 18.0, 1, 1),
    ]

    with app.app_context():
        db = get_db()
        for category in sample_categories:
            db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (category,))

        for product in sample_products:
            category_name = product[1]
            category_row = db.execute("SELECT id FROM categories WHERE name = ?", (category_name,)).fetchone()
            if category_row is None:
                continue
            db.execute(
                """
                INSERT OR IGNORE INTO products (
                    name, category_id, bottle_size_oz, cost, empty_bottle_weight, full_bottle_weight,
                    pour_spout_weight, uses_standard_weighing, low_stock_threshold_oz,
                    low_stock_threshold_unopened, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product[0],
                    category_row[0],
                    product[2],
                    product[3],
                    product[4],
                    product[5],
                    product[6],
                    product[7],
                    product[8],
                    product[9],
                    product[10],
                ),
            )
        db.commit()
