from app.services.decision_engine import DecisionEngine
from app.services.inventory_service import InventoryService


def _add_partial_supplier(db_session, scenario_one):
    from decimal import Decimal

    from app.models import Supplier, SupplierProduct

    supplier = Supplier(name="PartialCo Test", contact_email="partial@example.com", status="ACTIVE", reliability_score=Decimal("0.900"))
    db_session.add(supplier)
    db_session.flush()
    db_session.add(
        SupplierProduct(
            supplier_id=supplier.id,
            product_id=scenario_one["product"].id,
            unit_price=Decimal("49.00"),
            minimum_order_quantity=100,
            order_multiple=50,
            lead_time_days=1,
            available_quantity=250,
            active=True,
        )
    )
    db_session.commit()
    return supplier


def test_scenario_one_correct_modification(db_session, scenario_one):
    recommendation = scenario_one["recommendation"]
    decision, proposed = DecisionEngine(db_session).decide_for_recommendation(recommendation.id)

    assert decision.decision == "MODIFY"
    assert decision.original_quantity == 800
    assert decision.proposed_quantity == 650
    assert proposed is not None
    assert proposed.quantity == 650
    assert str(proposed.total_amount) == "32500.00"
    assert decision.requires_approval is True


def test_best_supplier_short_creates_split_actions_with_labels(db_session, scenario_one):
    partial_supplier = _add_partial_supplier(db_session, scenario_one)

    decision, actions = DecisionEngine(db_session).decide_actions_for_recommendation(scenario_one["recommendation"].id)

    assert decision.decision == "MODIFY"
    assert decision.proposed_quantity == 650
    assert len(actions) == 2
    assert sum(action.quantity for action in actions) == 650
    assert actions[0].supplier_id == partial_supplier.id
    assert actions[0].supplier_name == "PartialCo Test"
    assert actions[0].product_sku == "SKU-101"
    assert actions[0].product_name == "Product 1"
    assert actions[0].quantity == 250
    assert actions[1].supplier_id == scenario_one["supplier"].id
    assert actions[1].supplier_name == "Acme Wholesale"
    assert actions[1].quantity == 400
    assert any("Split sourcing" in evidence for evidence in decision.evidence)


def test_requirement_uses_timely_incoming_stock(db_session, scenario_one):
    product = scenario_one["product"]
    warehouse = scenario_one["warehouse"]

    requirement = InventoryService(db_session).calculate_purchase_requirement(product.id, warehouse.id, 14)

    assert requirement.sellable_inventory == 200
    assert requirement.forecast_demand == 900
    assert requirement.timely_incoming_quantity == 150
    assert requirement.required_quantity == 650


def test_no_feasible_supplier_decision_explains_failed_checks(db_session, scenario_one):
    from decimal import Decimal

    from app.models import PurchasingBudget

    budget = db_session.query(PurchasingBudget).filter_by(warehouse_id=scenario_one["warehouse"].id).one()
    budget.total_budget = Decimal("1000")
    db_session.commit()

    decision, proposed = DecisionEngine(db_session).decide_for_recommendation(scenario_one["recommendation"].id)

    assert decision.decision == "INVESTIGATE"
    assert proposed is None
    assert "No feasible supplier found" in decision.risks
    assert any("budget" in evidence.lower() for evidence in decision.evidence)

