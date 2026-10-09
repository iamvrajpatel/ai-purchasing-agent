from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import (
    DailySale,
    DemandForecast,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRecommendation,
    PurchasingBudget,
    Supplier,
    SupplierProduct,
    Warehouse,
)


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    name: str
    description: str
    category: str
    unit_volume: Decimal
    safety_stock: int


def upsert_one(db: Session, model, lookup: dict, values: dict):
    row = db.scalar(select(model).filter_by(**lookup))
    if row:
        for key, value in values.items():
            setattr(row, key, value)
        return row
    row = model(**lookup, **values)
    db.add(row)
    db.flush()
    return row


def seed_demo_data(db: Session) -> dict[str, int]:
    """Load deterministic retail purchasing data for demos.

    The data is deliberately realistic enough to show buyer tradeoffs while
    preserving the assignment's SKU-101 math: 800 recommended, 650 required.
    """
    today = date.today()
    budget_period = today.strftime("%Y-%m")

    products = _seed_products(db)
    warehouses = _seed_warehouses(db)
    suppliers = _seed_suppliers(db)
    _seed_inventory(db, products, warehouses)
    _seed_supplier_catalog(db, products, suppliers)
    _seed_budgets(db, warehouses, budget_period)
    _seed_forecasts_and_sales(db, products, warehouses, today)
    _seed_open_purchase_orders(db, products, warehouses, suppliers, today)
    _seed_recommendations(db, products, warehouses)
    db.commit()
    return {
        "products": len(products),
        "warehouses": len(warehouses),
        "suppliers": len(suppliers),
        "supplier_products": db.scalar(select(func.count(SupplierProduct.id))) or 0,
        "recommendations": db.scalar(select(func.count(PurchaseRecommendation.id))) or 0,
    }


def _seed_products(db: Session) -> dict[str, Product]:
    specs = [
        ProductSpec("SKU-101", "Organic Whole Milk 1L", "High-velocity chilled dairy staple", "Dairy", Decimal("1.00"), 100),
        ProductSpec("SKU-102", "Basmati Rice 5kg", "Premium long-grain rice bag", "Grocery", Decimal("3.20"), 80),
        ProductSpec("SKU-103", "Cold Brew Coffee 250ml", "Ready-to-drink refrigerated coffee", "Beverages", Decimal("0.35"), 120),
        ProductSpec("SKU-104", "Baby Diapers Medium 42ct", "Fast-moving baby care pack", "Baby Care", Decimal("2.80"), 60),
        ProductSpec("SKU-105", "Laundry Detergent 2L", "Household cleaning liquid", "Home Care", Decimal("2.50"), 50),
        ProductSpec("SKU-106", "Greek Yogurt 400g", "Short shelf-life chilled dairy", "Dairy", Decimal("0.60"), 90),
        ProductSpec("SKU-107", "Sparkling Water 6 Pack", "Bulky beverage multipack", "Beverages", Decimal("4.00"), 70),
        ProductSpec("SKU-108", "Olive Oil 1L", "Imported pantry item", "Grocery", Decimal("1.20"), 45),
        ProductSpec("SKU-109", "Protein Bar Chocolate", "Checkout impulse snack", "Snacks", Decimal("0.20"), 150),
        ProductSpec("SKU-110", "Toilet Paper 12 Roll", "Bulky household paper product", "Home Care", Decimal("5.50"), 65),
        ProductSpec("SKU-111", "Tomato Ketchup 950g", "Sauce and condiment staple", "Grocery", Decimal("0.90"), 55),
        ProductSpec("SKU-112", "Premium Dog Food 3kg", "Pet care recurring purchase", "Pet Care", Decimal("2.40"), 40),
    ]
    products: dict[str, Product] = {}
    for spec in specs:
        products[spec.sku] = upsert_one(
            db,
            Product,
            {"sku": spec.sku},
            {
                "name": spec.name,
                "description": spec.description,
                "category": spec.category,
                "unit_volume": spec.unit_volume,
                "safety_stock": spec.safety_stock,
                "active": True,
            },
        )
    return products


def _seed_warehouses(db: Session) -> dict[str, Warehouse]:
    specs = [
        ("NORTH-AHD", "North Fulfillment", "Ahmedabad", Decimal("7200")),
        ("WEST-MUM", "West Fulfillment", "Mumbai", Decimal("4800")),
        ("SOUTH-BLR", "South Fulfillment", "Bengaluru", Decimal("5600")),
    ]
    return {
        code: upsert_one(
            db,
            Warehouse,
            {"name": name},
            {"location": location, "total_storage_capacity": capacity, "active": True},
        )
        for code, name, location, capacity in specs
    }


def _seed_suppliers(db: Session) -> dict[str, Supplier]:
    specs = [
        ("acme", "Acme Wholesale", "ops@acme.example", "ACTIVE", Decimal("0.970")),
        ("bright", "Bright Supplies", "sales@bright.example", "ACTIVE", Decimal("0.910")),
        ("metro", "Metro Traders", "po@metro.example", "ACTIVE", Decimal("0.880")),
        ("partial", "PartialCo Distribution", "support@partial.example", "ACTIVE", Decimal("0.720")),
        ("fresh", "FreshChain Foods", "planner@freshchain.example", "ACTIVE", Decimal("0.940")),
        ("dormant", "Dormant Supplier", "closed@example", "INACTIVE", Decimal("0.400")),
    ]
    return {
        code: upsert_one(
            db,
            Supplier,
            {"name": name},
            {"contact_email": email, "status": status, "reliability_score": score},
        )
        for code, name, email, status, score in specs
    }


def _seed_inventory(db: Session, products: dict[str, Product], warehouses: dict[str, Warehouse]) -> None:
    inventory_specs = {
        ("SKU-101", "NORTH-AHD"): (260, 50, 10),
        ("SKU-102", "NORTH-AHD"): (780, 120, 5),
        ("SKU-103", "NORTH-AHD"): (90, 30, 2),
        ("SKU-104", "NORTH-AHD"): (420, 60, 4),
        ("SKU-105", "NORTH-AHD"): (180, 35, 0),
        ("SKU-106", "NORTH-AHD"): (75, 20, 3),
        ("SKU-107", "NORTH-AHD"): (130, 20, 0),
        ("SKU-108", "NORTH-AHD"): (210, 30, 0),
        ("SKU-109", "NORTH-AHD"): (640, 90, 10),
        ("SKU-110", "NORTH-AHD"): (60, 8, 0),
        ("SKU-111", "NORTH-AHD"): (240, 35, 0),
        ("SKU-112", "NORTH-AHD"): (130, 20, 0),
        ("SKU-101", "WEST-MUM"): (180, 45, 5),
        ("SKU-102", "WEST-MUM"): (360, 55, 0),
        ("SKU-103", "WEST-MUM"): (220, 40, 5),
        ("SKU-107", "WEST-MUM"): (340, 45, 0),
        ("SKU-110", "WEST-MUM"): (120, 15, 0),
        ("SKU-101", "SOUTH-BLR"): (210, 30, 5),
        ("SKU-104", "SOUTH-BLR"): (310, 70, 0),
        ("SKU-106", "SOUTH-BLR"): (95, 25, 0),
        ("SKU-109", "SOUTH-BLR"): (500, 60, 8),
    }
    for sku, product in products.items():
        for warehouse_code, warehouse in warehouses.items():
            on_hand, reserved, damaged = inventory_specs.get((sku, warehouse_code), (120, 15, 0))
            upsert_one(
                db,
                Inventory,
                {"product_id": product.id, "warehouse_id": warehouse.id},
                {
                    "on_hand_quantity": on_hand,
                    "reserved_quantity": reserved,
                    "damaged_quantity": damaged,
                    "version": 1,
                },
            )


def _seed_supplier_catalog(db: Session, products: dict[str, Product], suppliers: dict[str, Supplier]) -> None:
    specs = [
        ("acme", "SKU-101", "50.00", 100, 50, 3, 700),
        ("bright", "SKU-101", "54.00", 100, 25, 4, 1000),
        ("partial", "SKU-101", "49.00", 100, 50, 3, 250),
        ("fresh", "SKU-101", "52.25", 150, 50, 2, 450),
        ("acme", "SKU-102", "410.00", 50, 10, 6, 300),
        ("metro", "SKU-102", "398.00", 100, 50, 9, 1000),
        ("bright", "SKU-103", "42.00", 200, 100, 5, 500),
        ("fresh", "SKU-103", "45.00", 100, 50, 2, 180),
        ("metro", "SKU-104", "620.00", 40, 20, 6, 240),
        ("acme", "SKU-105", "310.00", 80, 40, 4, 600),
        ("fresh", "SKU-106", "78.00", 150, 50, 2, 500),
        ("bright", "SKU-107", "160.00", 100, 50, 7, 500),
        ("metro", "SKU-108", "520.00", 60, 20, 10, 220),
        ("acme", "SKU-109", "32.00", 300, 100, 4, 1600),
        ("bright", "SKU-110", "480.00", 50, 25, 8, 160),
        ("metro", "SKU-111", "90.00", 100, 50, 5, 800),
        ("acme", "SKU-112", "760.00", 40, 20, 7, 180),
    ]
    for supplier_code, sku, price, moq, multiple, lead_time, available in specs:
        upsert_one(
            db,
            SupplierProduct,
            {"supplier_id": suppliers[supplier_code].id, "product_id": products[sku].id},
            {
                "unit_price": Decimal(price),
                "minimum_order_quantity": moq,
                "order_multiple": multiple,
                "lead_time_days": lead_time,
                "available_quantity": available,
                "active": True,
            },
        )


def _seed_budgets(db: Session, warehouses: dict[str, Warehouse], budget_period: str) -> None:
    specs = {
        "NORTH-AHD": ("35000.00", "0.00", "0.00"),
        "WEST-MUM": ("48000.00", "8000.00", "12000.00"),
        "SOUTH-BLR": ("42000.00", "3000.00", "15000.00"),
    }
    for code, warehouse in warehouses.items():
        total, reserved, committed = specs[code]
        upsert_one(
            db,
            PurchasingBudget,
            {"warehouse_id": warehouse.id, "budget_period": budget_period},
            {
                "total_budget": Decimal(total),
                "reserved_amount": Decimal(reserved),
                "committed_amount": Decimal(committed),
                "version": 1,
            },
        )


def _seed_forecasts_and_sales(db: Session, products: dict[str, Product], warehouses: dict[str, Warehouse], today: date) -> None:
    for product in products.values():
        db.execute(delete(DemandForecast).where(DemandForecast.product_id == product.id))
        db.execute(delete(DailySale).where(DailySale.product_id == product.id))

    forecast_patterns = {
        "SKU-101": [70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 50, 50, 50, 50],
        "SKU-102": [35, 35, 40, 40, 45, 45, 50, 35, 35, 40, 45, 45, 50, 60],
        "SKU-103": [55, 60, 65, 85, 95, 100, 110, 90, 85, 80, 75, 70, 70, 70],
        "SKU-104": [20, 20, 22, 22, 25, 25, 25, 22, 22, 22, 24, 24, 24, 24],
        "SKU-105": [28, 28, 28, 30, 30, 35, 35, 28, 28, 30, 30, 35, 35, 40],
        "SKU-106": [42, 45, 45, 48, 50, 52, 55, 44, 44, 44, 46, 48, 50, 52],
        "SKU-107": [18, 20, 20, 24, 26, 28, 30, 20, 20, 24, 26, 28, 30, 32],
        "SKU-108": [12, 12, 14, 14, 14, 16, 16, 12, 12, 14, 14, 16, 16, 16],
        "SKU-109": [85, 90, 95, 95, 100, 105, 110, 90, 90, 95, 100, 105, 110, 115],
        "SKU-110": [14, 16, 16, 18, 20, 22, 24, 16, 16, 18, 20, 22, 24, 24],
        "SKU-111": [24, 24, 26, 26, 28, 28, 30, 24, 24, 26, 26, 28, 30, 30],
        "SKU-112": [10, 10, 12, 12, 12, 14, 14, 10, 10, 12, 12, 14, 14, 16],
    }
    for sku, product in products.items():
        base_pattern = forecast_patterns[sku]
        for warehouse_code, warehouse in warehouses.items():
            multiplier = Decimal("1.0") if warehouse_code == "NORTH-AHD" else Decimal("0.65") if warehouse_code == "WEST-MUM" else Decimal("0.75")
            for offset, quantity in enumerate(base_pattern):
                db.add(
                    DemandForecast(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        forecast_date=today + timedelta(days=offset),
                        expected_quantity=max(1, int(Decimal(quantity) * multiplier)),
                    )
                )
            for offset in range(28):
                recent_boost = 1.55 if sku == "SKU-103" and offset < 7 else 1.0
                units = max(1, int(Decimal(base_pattern[offset % len(base_pattern)]) * multiplier * Decimal(str(recent_boost)) * Decimal("0.82")))
                db.add(
                    DailySale(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        sales_date=today - timedelta(days=offset + 1),
                        units_sold=units,
                    )
                )


def _seed_open_purchase_orders(
    db: Session,
    products: dict[str, Product],
    warehouses: dict[str, Warehouse],
    suppliers: dict[str, Supplier],
    today: date,
) -> None:
    specs = [
        ("seed-incoming-sku101-150", "bright", "NORTH-AHD", "SKU-101", 150, "54.00", 1, "CONFIRMED"),
        ("seed-late-sku103-300", "bright", "NORTH-AHD", "SKU-103", 300, "42.00", 12, "CONFIRMED"),
        ("seed-west-sku107-100", "bright", "WEST-MUM", "SKU-107", 100, "160.00", 5, "CONFIRMED"),
        ("seed-south-sku104-80", "metro", "SOUTH-BLR", "SKU-104", 80, "620.00", 4, "PENDING"),
    ]
    for idem, supplier_code, warehouse_code, sku, qty, unit_price, days, supplier_status in specs:
        total = Decimal(qty) * Decimal(unit_price)
        order = upsert_one(
            db,
            PurchaseOrder,
            {"idempotency_key": idem},
            {
                "supplier_id": suppliers[supplier_code].id,
                "warehouse_id": warehouses[warehouse_code].id,
                "status": "OPEN",
                "supplier_confirmation_status": supplier_status,
                "supplier_response_json": {"status": supplier_status, "confirmed_quantity": qty if supplier_status == "CONFIRMED" else None},
                "expected_delivery_date": today + timedelta(days=days),
                "total_amount": total,
                "source_recommendation_id": None,
                "agent_run_id": None,
                "external_reference": idem.replace("seed-", "demo-po-"),
            },
        )
        _replace_order_item(db, order, products[sku], qty, Decimal(unit_price), total)


def _replace_order_item(db: Session, order: PurchaseOrder, product: Product, qty: int, unit_price: Decimal, total: Decimal) -> None:
    if order.id:
        db.execute(delete(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == order.id))
        db.flush()
    order.items.append(PurchaseOrderItem(product_id=product.id, quantity=qty, unit_price=unit_price, line_total=total))


def _seed_recommendations(db: Session, products: dict[str, Product], warehouses: dict[str, Warehouse]) -> None:
    specs = [
        ("SKU-101", "NORTH-AHD", 800, "SYSTEM_REPLENISHMENT"),
        ("SKU-102", "NORTH-AHD", 300, "WEEKLY_BUY_PLAN"),
        ("SKU-103", "NORTH-AHD", 500, "DEMAND_SPIKE_ALERT"),
        ("SKU-107", "WEST-MUM", 250, "BULKY_ITEM_REVIEW"),
        ("SKU-110", "NORTH-AHD", 200, "STORAGE_CONSTRAINT_REVIEW"),
        ("SKU-108", "SOUTH-BLR", 120, "LONG_LEAD_TIME_REVIEW"),
    ]
    for sku, warehouse_code, qty, source in specs:
        upsert_one(
            db,
            PurchaseRecommendation,
            {"product_id": products[sku].id, "warehouse_id": warehouses[warehouse_code].id},
            {"recommended_quantity": qty, "recommendation_source": source, "status": "PENDING"},
        )


def _safe_database_url() -> str:
    value = get_settings().database_url
    if "@" not in value:
        return value
    prefix, rest = value.split("@", 1)
    if ":" not in prefix:
        return value
    return prefix.rsplit(":", 1)[0] + ":***@" + rest


def ingest_demo_data() -> None:
    db = SessionLocal()
    try:
        summary = seed_demo_data(db)
    except OperationalError as exc:
        print("Could not connect to PostgreSQL.")
        print(f"Configured DATABASE_URL: {_safe_database_url()}")
        print("Start PostgreSQL and run migrations before ingesting demo data.")
        print("Example: docker compose up -d postgres")
        raise SystemExit(1) from exc
    finally:
        db.close()
    print(
        "Demo data loaded: "
        f"{summary['products']} products, "
        f"{summary['warehouses']} warehouses, "
        f"{summary['suppliers']} suppliers, "
        f"{summary['supplier_products']} supplier-product rows, "
        f"{summary['recommendations']} recommendations."
    )


if __name__ == "__main__":
    ingest_demo_data()

