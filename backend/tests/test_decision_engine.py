from app.services.decision_engine import DecisionEngine
from app.services.inventory_service import InventoryService


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

