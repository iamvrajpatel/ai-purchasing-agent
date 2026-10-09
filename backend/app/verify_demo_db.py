from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import (
    DemandForecast,
    Inventory,
    Product,
    PurchaseOrder,
    PurchaseRecommendation,
    PurchasingBudget,
    Supplier,
    SupplierProduct,
    Warehouse,
)
from app.repositories.inventory_repository import InventoryRepository


def _safe_database_url() -> str:
    value = get_settings().database_url
    if "@" not in value:
        return value
    prefix, rest = value.split("@", 1)
    if ":" not in prefix:
        return value
    return prefix.rsplit(":", 1)[0] + ":***@" + rest


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count(model.id))) or 0


def verify_demo_database() -> None:
    db = SessionLocal()
    try:
        counts = {
            "products": _count(db, Product),
            "warehouses": _count(db, Warehouse),
            "inventory": _count(db, Inventory),
            "suppliers": _count(db, Supplier),
            "supplier_products": _count(db, SupplierProduct),
            "forecasts": _count(db, DemandForecast),
            "budgets": _count(db, PurchasingBudget),
            "open_purchase_orders": _count(db, PurchaseOrder),
            "recommendations": _count(db, PurchaseRecommendation),
        }
        print("Demo database counts:")
        for name, value in counts.items():
            print(f"  {name}: {value}")

        if counts["supplier_products"] == 0:
            print("\nERROR: supplier_products has no rows. The agent cannot select suppliers.")
            print("Run: python app/reset_demo_db.py")
            raise SystemExit(2)

        print("\nSupplier options by recommendation:")
        rows = db.execute(
            select(
                PurchaseRecommendation.id,
                Product.sku,
                Product.name,
                func.count(SupplierProduct.id),
            )
            .join(Product, Product.id == PurchaseRecommendation.product_id)
            .outerjoin(
                SupplierProduct,
                (SupplierProduct.product_id == PurchaseRecommendation.product_id)
                & (SupplierProduct.active.is_(True)),
            )
            .group_by(PurchaseRecommendation.id, Product.sku, Product.name)
            .order_by(PurchaseRecommendation.id)
        ).all()

        missing = False
        for recommendation_id, sku, name, option_count in rows:
            status = "OK" if option_count else "MISSING"
            print(f"  Recommendation #{recommendation_id} {sku} {name}: {option_count} supplier option(s) [{status}]")
            missing = missing or option_count == 0

        if missing:
            print("\nERROR: one or more recommendations have no supplier options.")
            print("Run: python app/reset_demo_db.py")
            raise SystemExit(2)

        print("\nWarehouse capacity:")
        inventory_repo = InventoryRepository(db)
        over_capacity = False
        for warehouse in db.scalars(select(Warehouse).order_by(Warehouse.name)):
            occupied = inventory_repo.current_warehouse_occupied_volume(warehouse.id)
            available = warehouse.total_storage_capacity - occupied
            status = "OK" if available >= 0 else "OVER_CAPACITY"
            print(
                f"  {warehouse.name}: occupied {occupied} / capacity {warehouse.total_storage_capacity} "
                f"(available {available}) [{status}]"
            )
            over_capacity = over_capacity or available < 0

        if over_capacity:
            print("\nERROR: one or more warehouses start over capacity.")
            print("Run: python app/reset_demo_db.py")
            raise SystemExit(2)

        print("\nDemo database looks ready for agent analysis.")
    except OperationalError as exc:
        print("Could not connect to PostgreSQL.")
        print(f"Configured DATABASE_URL: {_safe_database_url()}")
        raise SystemExit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    verify_demo_database()

