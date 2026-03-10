from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Dict, Optional

from flask import Flask, Response, flash, redirect, render_template, request, url_for

from db import close_db, get_db, init_db, seed_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-local-key"
    app.teardown_appcontext(close_db)

    @app.route("/")
    def dashboard():
        db = get_db()
        total_products = db.execute("SELECT COUNT(*) AS c FROM products WHERE is_active = 1").fetchone()["c"]

        latest_rows = _get_latest_inventory_rows()
        low_stock_count = sum(
            1
            for row in latest_rows
            if row["total_stock_on_hand_oz"] <= row["low_stock_threshold_oz"]
            or row["unopened_bottle_count"] <= row["low_stock_threshold_unopened"]
        )

        recent_entries = db.execute(
            """
            SELECT di.inventory_date, p.name, di.total_stock_on_hand_oz, di.unopened_bottle_count
            FROM daily_inventory di
            JOIN products p ON p.id = di.product_id
            ORDER BY di.inventory_date DESC, p.name
            LIMIT 10
            """
        ).fetchall()

        recent_deliveries = db.execute(
            """
            SELECT rd.delivery_date, p.name, rd.quantity_received, rd.unit_cost
            FROM restock_deliveries rd
            JOIN products p ON p.id = rd.product_id
            ORDER BY rd.delivery_date DESC
            LIMIT 10
            """
        ).fetchall()

        return render_template(
            "dashboard.html",
            total_products=total_products,
            low_stock_count=low_stock_count,
            recent_entries=recent_entries,
            recent_deliveries=recent_deliveries,
        )

    @app.route("/products")
    def products():
        db = get_db()
        rows = db.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            JOIN categories c ON c.id = p.category_id
            ORDER BY c.name, p.name
            """
        ).fetchall()
        return render_template("products.html", products=rows)

    @app.route("/products/new", methods=["GET", "POST"])
    def new_product():
        db = get_db()
        categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

        if request.method == "POST":
            form = request.form
            name = form.get("name", "").strip()
            if not name:
                flash("Product name is required.", "error")
                return render_template("product_form.html", categories=categories)

            category_id = _parse_int(form.get("category_id"), "Category")
            bottle_size_oz = _parse_float(form.get("bottle_size_oz"), "Bottle size")
            cost = _parse_float(form.get("cost"), "Cost")
            empty_bottle_weight = _parse_float(form.get("empty_bottle_weight"), "Empty bottle weight")
            full_bottle_weight = _parse_float(form.get("full_bottle_weight"), "Full bottle weight")
            pour_spout = form.get("pour_spout_weight")
            pour_spout_weight = _parse_float(pour_spout, "Pour spout weight", allow_blank=True)
            low_oz = _parse_float(form.get("low_stock_threshold_oz"), "Low-stock ounce threshold", default=0.0)
            low_unopened = _parse_int(
                form.get("low_stock_threshold_unopened"), "Low-stock unopened threshold", default=0
            )

            if None in (category_id, bottle_size_oz, cost, empty_bottle_weight, full_bottle_weight, low_oz, low_unopened):
                return render_template("product_form.html", categories=categories)

            if full_bottle_weight <= empty_bottle_weight:
                flash("Full bottle weight must be greater than empty bottle weight.", "error")
                return render_template("product_form.html", categories=categories)

            try:
                db.execute(
                    """
                    INSERT INTO products (
                        name, category_id, bottle_size_oz, cost,
                        empty_bottle_weight, full_bottle_weight, pour_spout_weight,
                        uses_standard_weighing, low_stock_threshold_oz,
                        low_stock_threshold_unopened, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        category_id,
                        bottle_size_oz,
                        cost,
                        empty_bottle_weight,
                        full_bottle_weight,
                        pour_spout_weight,
                        1 if form.get("uses_standard_weighing") else 0,
                        low_oz,
                        low_unopened,
                        1 if form.get("is_active") else 0,
                    ),
                )
                db.commit()
            except Exception as exc:
                flash(f"Could not save product: {exc}", "error")
                return render_template("product_form.html", categories=categories)

            flash("Product added.", "success")
            return redirect(url_for("products"))

        return render_template("product_form.html", categories=categories)

    @app.route("/daily-entry", methods=["GET", "POST"])
    def daily_entry():
        db = get_db()
        categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
        products = db.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.is_active = 1
            ORDER BY c.name, p.name
            """
        ).fetchall()

        if request.method == "POST":
            form = request.form
            inventory_date = form.get("inventory_date") or str(date.today())
            product_id = _parse_int(form.get("product_id"), "Product")
            unopened_count = _parse_int(form.get("unopened_bottle_count"), "Unopened bottle count", default=0)
            manual_opened_oz = _parse_float(form.get("manual_opened_ounces"), "Manual opened ounces", default=0.0)
            notes = form.get("notes", "").strip() or None

            if None in (product_id, unopened_count, manual_opened_oz):
                return render_template("daily_entry.html", categories=categories, products=products, today=str(date.today()))

            product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not product:
                flash("Invalid product.", "error")
                return redirect(url_for("daily_entry"))

            total_opened_oz = manual_opened_oz
            weighins = []

            for idx in range(1, 9):
                weight_raw = form.get(f"measured_weight_{idx}")
                bottle_id = (form.get(f"bottle_identifier_{idx}") or "").strip() or None
                if not weight_raw:
                    continue
                measured_weight = _parse_float(weight_raw, f"Measured weight {idx}")
                if measured_weight is None:
                    return render_template("daily_entry.html", categories=categories, products=products, today=str(date.today()))
                estimated_oz = _estimate_open_ounces(product, measured_weight)
                total_opened_oz += estimated_oz
                weighins.append((bottle_id, measured_weight, estimated_oz))

            total_opened_oz = round(total_opened_oz, 2)
            total_stock = round(unopened_count * float(product["bottle_size_oz"]) + total_opened_oz, 2)

            existing = db.execute(
                "SELECT id FROM daily_inventory WHERE inventory_date = ? AND product_id = ?",
                (inventory_date, product_id),
            ).fetchone()

            if existing:
                di_id = existing["id"]
                db.execute(
                    """
                    UPDATE daily_inventory
                    SET unopened_bottle_count = ?,
                        total_opened_ounces_remaining = ?,
                        total_stock_on_hand_oz = ?,
                        notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (unopened_count, total_opened_oz, total_stock, notes, di_id),
                )
                db.execute("DELETE FROM open_bottle_weighins WHERE daily_inventory_id = ?", (di_id,))
                action = "updated"
            else:
                cursor = db.execute(
                    """
                    INSERT INTO daily_inventory (
                        inventory_date, product_id, unopened_bottle_count,
                        total_opened_ounces_remaining, total_stock_on_hand_oz, notes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (inventory_date, product_id, unopened_count, total_opened_oz, total_stock, notes),
                )
                di_id = cursor.lastrowid
                action = "saved"

            for bottle_id, measured_weight, estimated_oz in weighins:
                db.execute(
                    """
                    INSERT INTO open_bottle_weighins (
                        daily_inventory_id, inventory_date, product_id,
                        bottle_identifier, measured_bottle_weight, estimated_ounces_remaining
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (di_id, inventory_date, product_id, bottle_id, measured_weight, estimated_oz),
                )

            db.commit()
            flash(f"Daily inventory {action}.", "success")
            return redirect(url_for("daily_entry"))

        return render_template("daily_entry.html", categories=categories, products=products, today=str(date.today()))

    @app.route("/inventory/current")
    def current_inventory():
        return render_template("current_inventory.html", rows=_get_latest_inventory_rows())

    @app.route("/inventory/history")
    def inventory_history():
        db = get_db()
        rows = db.execute(
            """
            SELECT di.inventory_date, c.name AS category_name, p.name,
                   di.unopened_bottle_count, di.total_opened_ounces_remaining,
                   di.total_stock_on_hand_oz, di.notes
            FROM daily_inventory di
            JOIN products p ON p.id = di.product_id
            JOIN categories c ON c.id = p.category_id
            ORDER BY di.inventory_date DESC, c.name, p.name
            LIMIT 300
            """
        ).fetchall()
        return render_template("inventory_history.html", rows=rows)

    @app.route("/restock", methods=["GET", "POST"])
    def restock_entry():
        db = get_db()
        products = db.execute("SELECT id, name FROM products WHERE is_active = 1 ORDER BY name").fetchall()

        if request.method == "POST":
            form = request.form
            delivery_date = form.get("delivery_date") or str(date.today())
            product_id = _parse_int(form.get("product_id"), "Product")
            qty = _parse_int(form.get("quantity_received"), "Quantity received")
            unit_cost = _parse_float(form.get("unit_cost"), "Unit cost")
            notes = form.get("notes", "").strip() or None

            if None in (product_id, qty, unit_cost):
                return render_template("restock.html", products=products, history=_restock_history(), today=str(date.today()))

            db.execute(
                """
                INSERT INTO restock_deliveries (delivery_date, product_id, quantity_received, unit_cost, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (delivery_date, product_id, qty, unit_cost, notes),
            )
            db.commit()
            flash("Restock delivery saved.", "success")
            return redirect(url_for("restock_entry"))

        return render_template("restock.html", products=products, history=_restock_history(), today=str(date.today()))

    @app.route("/alerts/low-stock")
    def low_stock_alerts():
        rows = [
            row
            for row in _get_latest_inventory_rows()
            if row["total_stock_on_hand_oz"] <= row["low_stock_threshold_oz"]
            or row["unopened_bottle_count"] <= row["low_stock_threshold_unopened"]
        ]
        return render_template("low_stock.html", rows=rows)

    @app.route("/forecast")
    def forecast():
        rows = _get_latest_inventory_rows()
        modeled = []
        for row in rows:
            usage = _rolling_usage_5_weeks(row["product_id"])
            days_left = 0
            if usage["avg_daily_usage_oz"] > 0:
                days_left = round(row["total_stock_on_hand_oz"] / usage["avg_daily_usage_oz"], 1)
            modeled.append({**dict(row), **usage, "days_left": days_left})
        return render_template("forecast.html", rows=modeled)

    @app.route("/reports/current-inventory.csv")
    def export_current_inventory_csv():
        rows = _get_latest_inventory_rows()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Category", "Product", "Inventory Date", "Unopened Bottles", "Opened Oz", "Total Stock Oz"])
        for row in rows:
            writer.writerow(
                [
                    row["category_name"],
                    row["name"],
                    row["inventory_date"],
                    row["unopened_bottle_count"],
                    row["total_opened_ounces_remaining"],
                    row["total_stock_on_hand_oz"],
                ]
            )

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=current_inventory.csv"},
        )

    @app.route("/setup/init")
    def setup_init():
        init_db(app)
        seed_db(app)
        flash("Database initialized and seeded.", "success")
        return redirect(url_for("dashboard"))

    return app


def _restock_history():
    db = get_db()
    return db.execute(
        """
        SELECT rd.*, p.name AS product_name
        FROM restock_deliveries rd
        JOIN products p ON p.id = rd.product_id
        ORDER BY rd.delivery_date DESC, rd.id DESC
        LIMIT 30
        """
    ).fetchall()


def _parse_float(value: Optional[str], label: str, *, allow_blank: bool = False, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        if allow_blank:
            return None
        return default
    try:
        number = float(value)
    except ValueError:
        flash(f"{label} must be a number.", "error")
        return None
    if number < 0:
        flash(f"{label} cannot be negative.", "error")
        return None
    return number


def _parse_int(value: Optional[str], label: str, *, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except ValueError:
        flash(f"{label} must be a whole number.", "error")
        return None
    if number < 0:
        flash(f"{label} cannot be negative.", "error")
        return None
    return number


def _get_latest_inventory_rows():
    db = get_db()
    return db.execute(
        """
        WITH latest AS (
            SELECT di.*
            FROM daily_inventory di
            JOIN (
                SELECT product_id, MAX(inventory_date) AS max_date
                FROM daily_inventory
                GROUP BY product_id
            ) m ON m.product_id = di.product_id AND m.max_date = di.inventory_date
        )
        SELECT l.inventory_date, p.id AS product_id, p.name, c.name AS category_name,
               p.bottle_size_oz, p.low_stock_threshold_oz, p.low_stock_threshold_unopened,
               l.unopened_bottle_count, l.total_opened_ounces_remaining, l.total_stock_on_hand_oz
        FROM latest l
        JOIN products p ON p.id = l.product_id
        JOIN categories c ON c.id = p.category_id
        WHERE p.is_active = 1
        ORDER BY c.name, p.name
        """
    ).fetchall()


def _estimate_open_ounces(product, measured_weight: float) -> float:
    empty_weight = float(product["empty_bottle_weight"])
    full_weight = float(product["full_bottle_weight"])
    bottle_size_oz = float(product["bottle_size_oz"])

    if full_weight <= empty_weight:
        return 0.0

    ratio = (measured_weight - empty_weight) / (full_weight - empty_weight)
    ratio = max(0.0, min(1.0, ratio))
    return round(ratio * bottle_size_oz, 2)


def _rolling_usage_5_weeks(product_id: int) -> Dict[str, float]:
    db = get_db()
    end_date = date.today()
    start_date = end_date - timedelta(days=35)

    rows = db.execute(
        """
        SELECT inventory_date, total_stock_on_hand_oz
        FROM daily_inventory
        WHERE product_id = ?
          AND inventory_date BETWEEN ? AND ?
        ORDER BY inventory_date ASC
        """,
        (product_id, str(start_date), str(end_date)),
    ).fetchall()

    total_depletion = 0.0
    periods = 0
    previous = None
    for row in rows:
        stock = float(row["total_stock_on_hand_oz"])
        if previous is not None:
            depletion = previous - stock
            if depletion > 0:
                total_depletion += depletion
            periods += 1
        previous = stock

    avg_daily_usage = round(total_depletion / periods, 2) if periods else 0.0
    return {
        "avg_daily_usage_oz": avg_daily_usage,
        "projected_weekly_usage_oz": round(avg_daily_usage * 7, 2),
    }


app = create_app()

if __name__ == "__main__":
    init_db(app)
    seed_db(app)
    app.run(debug=True)
