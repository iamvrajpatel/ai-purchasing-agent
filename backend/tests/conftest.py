from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import (
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


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def scenario_one(db_session):
    today = date.today()
    product = Product(sku="SKU-101", name="Product 1", description="Scenario product", category="Grocery", unit_volume=Decimal("1"), safety_stock=100)
    warehouse = Warehouse(name="North Fulfillment", location="Ahmedabad", total_storage_capacity=Decimal("1500"), active=True)
    supplier = Supplier(name="Acme Wholesale", contact_email="ops@example.com", status="ACTIVE", reliability_score=Decimal("0.970"))
    db_session.add_all([product, warehouse, supplier])
    db_session.flush()
    db_session.add(Inventory(product_id=product.id, warehouse_id=warehouse.id, on_hand_quantity=260, reserved_quantity=50, damaged_quantity=10))
    db_session.add(
        SupplierProduct(
            supplier_id=supplier.id,
            product_id=product.id,
            unit_price=Decimal("50.00"),
            minimum_order_quantity=100,
            order_multiple=50,
            lead_time_days=1,
            available_quantity=700,
            active=True,
        )
    )
    db_session.add(
        PurchasingBudget(
            warehouse_id=warehouse.id,
            budget_period=today.strftime("%Y-%m"),
            total_budget=Decimal("35000"),
            reserved_amount=Decimal("0"),
            committed_amount=Decimal("0"),
        )
    )
    daily = [70, 70, 70, 70, 70, 70, 70, 70, 70, 70, 50, 50, 50, 50]
    for offset, qty in enumerate(daily):
        db_session.add(DemandForecast(product_id=product.id, warehouse_id=warehouse.id, forecast_date=today + timedelta(days=offset), expected_quantity=qty))
    incoming = PurchaseOrder(
        supplier_id=supplier.id,
        warehouse_id=warehouse.id,
        status="OPEN",
        supplier_confirmation_status="CONFIRMED",
        expected_delivery_date=today,
        total_amount=Decimal("7500"),
        idempotency_key="incoming",
    )
    incoming.items.append(PurchaseOrderItem(product_id=product.id, quantity=150, unit_price=Decimal("50"), line_total=Decimal("7500")))
    db_session.add(incoming)
    recommendation = PurchaseRecommendation(product_id=product.id, warehouse_id=warehouse.id, recommended_quantity=800, recommendation_source="SYSTEM", status="PENDING")
    db_session.add(recommendation)
    db_session.commit()
    return {"product": product, "warehouse": warehouse, "supplier": supplier, "recommendation": recommendation}

