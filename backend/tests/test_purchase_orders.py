from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import AgentRun, ApprovalRequest, PurchasingBudget
from app.schemas.purchasing import ProposedAction
from app.integrations.mock_supplier import SupplierSubmissionResult, MockSupplierClient
from app.services.approval_service import ApprovalService
from app.services.purchase_order_service import PurchaseOrderService


def _approved_run(db_session, scenario_one, quantity=650):
    recommendation = scenario_one["recommendation"]
    supplier = scenario_one["supplier"]
    proposed = ProposedAction(
        recommendation_id=recommendation.id,
        product_id=scenario_one["product"].id,
        warehouse_id=scenario_one["warehouse"].id,
        supplier_id=supplier.id,
        quantity=quantity,
        unit_price=Decimal("50"),
        total_amount=Decimal(quantity) * Decimal("50"),
        expected_delivery_date=datetime.now(timezone.utc).date() + timedelta(days=1),
        decision="MODIFY",
    )
    run = AgentRun(
        recommendation_id=recommendation.id,
        status="APPROVED",
        decision="MODIFY",
        original_quantity=800,
        proposed_quantity=quantity,
        proposed_supplier_id=supplier.id,
        reasoning="test",
        evidence_snapshot={"proposed_action": proposed.model_dump(mode="json")},
    )
    db_session.add(run)
    db_session.flush()
    approval = ApprovalRequest(agent_run_id=run.id, proposed_action_json=proposed.model_dump(mode="json"), status="PENDING")
    db_session.add(approval)
    db_session.commit()
    ApprovalService(db_session).approve(approval.id, "buyer@example.com")
    db_session.commit()
    return run


def test_duplicate_execution_creates_one_order(db_session, scenario_one):
    run = _approved_run(db_session, scenario_one)

    service = PurchaseOrderService(db_session)
    first = service.execute_agent_run(run.id)
    db_session.commit()
    second = service.execute_agent_run(run.id)
    db_session.commit()

    assert first.id == second.id


def test_budget_change_after_approval_stops_execution(db_session, scenario_one):
    run = _approved_run(db_session, scenario_one)
    budget = db_session.query(PurchasingBudget).one()
    budget.total_budget = Decimal("100")
    db_session.commit()

    try:
        PurchaseOrderService(db_session).execute_agent_run(run.id)
    except Exception as exc:
        assert "revalidation" in str(exc).lower() or "budget" in str(exc).lower()
    else:
        raise AssertionError("Execution should have stopped")


def test_partial_supplier_fulfillment_is_detected(db_session, scenario_one, monkeypatch):
    def partial_submit(self, supplier_id, product_id, quantity, idempotency_key):
        return SupplierSubmissionResult(
            status="PARTIALLY_CONFIRMED",
            confirmed_quantity=250,
            external_reference="partial-test",
            response={"status": "PARTIALLY_CONFIRMED", "requested_quantity": quantity, "confirmed_quantity": 250},
        )

    monkeypatch.setattr(MockSupplierClient, "submit_purchase_order", partial_submit)
    run = _approved_run(db_session, scenario_one)

    order = PurchaseOrderService(db_session).execute_agent_run(run.id)
    db_session.commit()

    assert order.supplier_confirmation_status == "PARTIALLY_CONFIRMED"
    assert order.status == "VALIDATION_FAILED"

