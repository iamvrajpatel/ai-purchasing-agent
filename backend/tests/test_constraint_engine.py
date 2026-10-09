from decimal import Decimal

from app.models import PurchasingBudget, SupplierProduct, Warehouse
from app.services.inventory_service import InventoryService
from app.services.constraint_engine import ConstraintEngine


def test_budget_restriction_blocks_execution(db_session, scenario_one):
    warehouse = scenario_one["warehouse"]
    budget = db_session.query(PurchasingBudget).filter_by(warehouse_id=warehouse.id).one()
    budget.total_budget = Decimal("1000")
    db_session.commit()

    result = ConstraintEngine(db_session).evaluate(
        scenario_one["product"].id,
        warehouse.id,
        scenario_one["supplier"].id,
        650,
    )

    assert result.valid is False
    assert any(v.code == "BUDGET_EXCEEDED" for v in result.violations)


def test_moq_violation_blocks_purchase(db_session, scenario_one):
    supplier_product = db_session.query(SupplierProduct).one()
    supplier_product.minimum_order_quantity = 1000
    db_session.commit()

    result = ConstraintEngine(db_session).evaluate(
        scenario_one["product"].id,
        scenario_one["warehouse"].id,
        scenario_one["supplier"].id,
        650,
    )

    assert result.valid is False
    assert any(v.code == "MOQ_VIOLATION" for v in result.violations)


def test_storage_restriction_blocks_purchase(db_session, scenario_one):
    warehouse = db_session.get(Warehouse, scenario_one["warehouse"].id)
    warehouse.total_storage_capacity = Decimal("400")
    db_session.commit()

    result = ConstraintEngine(db_session).evaluate(
        scenario_one["product"].id,
        warehouse.id,
        scenario_one["supplier"].id,
        650,
    )

    assert result.valid is False
    assert any(v.code == "STORAGE_CAPACITY_EXCEEDED" for v in result.violations)


def test_storage_snapshot_uses_volume_not_raw_units(db_session, scenario_one):
    product = scenario_one["product"]
    product.unit_volume = Decimal("2.5")
    db_session.commit()

    snapshot = InventoryService(db_session).storage_capacity_snapshot(scenario_one["warehouse"].id)

    assert snapshot["current_occupancy_units"] == 260
    assert snapshot["current_occupied_volume"] == "650.0000"

