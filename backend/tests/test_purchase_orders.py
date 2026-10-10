from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import AgentRun, ApprovalRequest, PurchaseOrderRecoveryCase, PurchasingBudget
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


def _approved_split_run(db_session, scenario_one):
    recommendation = scenario_one["recommendation"]
    product = scenario_one["product"]
    warehouse = scenario_one["warehouse"]
    supplier = scenario_one["supplier"]
    from app.models import Supplier, SupplierProduct

    second_supplier = Supplier(name="Backup Split Supplier", contact_email="backup@example.com", status="ACTIVE", reliability_score=Decimal("0.910"))
    db_session.add(second_supplier)
    db_session.flush()
    db_session.add(
        SupplierProduct(
            supplier_id=second_supplier.id,
            product_id=product.id,
            unit_price=Decimal("51.00"),
            minimum_order_quantity=100,
            order_multiple=50,
            lead_time_days=1,
            available_quantity=500,
            active=True,
        )
    )
    actions = [
        ProposedAction(
            recommendation_id=recommendation.id,
            product_id=product.id,
            product_sku=product.sku,
            product_name=product.name,
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            quantity=250,
            unit_price=Decimal("50"),
            total_amount=Decimal("12500"),
            expected_delivery_date=datetime.now(timezone.utc).date() + timedelta(days=1),
            decision="MODIFY",
        ),
        ProposedAction(
            recommendation_id=recommendation.id,
            product_id=product.id,
            product_sku=product.sku,
            product_name=product.name,
            warehouse_id=warehouse.id,
            warehouse_name=warehouse.name,
            supplier_id=second_supplier.id,
            supplier_name=second_supplier.name,
            quantity=400,
            unit_price=Decimal("51"),
            total_amount=Decimal("20400"),
            expected_delivery_date=datetime.now(timezone.utc).date() + timedelta(days=1),
            decision="MODIFY",
        ),
    ]
    run = AgentRun(
        recommendation_id=recommendation.id,
        status="AWAITING_APPROVAL",
        decision="MODIFY",
        original_quantity=800,
        proposed_quantity=650,
        proposed_supplier_id=None,
        reasoning="split test",
        evidence_snapshot={
            "proposed_action": actions[0].model_dump(mode="json"),
            "proposed_actions": [action.model_dump(mode="json") for action in actions],
        },
    )
    db_session.add(run)
    db_session.flush()
    for action in actions:
        db_session.add(ApprovalRequest(agent_run_id=run.id, proposed_action_json=action.model_dump(mode="json"), status="PENDING"))
    db_session.commit()
    approvals = db_session.query(ApprovalRequest).filter_by(agent_run_id=run.id).order_by(ApprovalRequest.id).all()
    for approval in approvals:
        ApprovalService(db_session).approve(approval.id, "buyer@example.com")
    db_session.commit()
    return run, approvals


def _pending_split_run(db_session, scenario_one):
    run, approvals = _approved_split_run(db_session, scenario_one)
    for approval in approvals:
        approval.status = "PENDING"
        approval.approved_by = None
        approval.approved_at = None
    run.status = "AWAITING_APPROVAL"
    db_session.commit()
    return run, approvals


def test_duplicate_execution_creates_one_order(db_session, scenario_one):
    run = _approved_run(db_session, scenario_one)

    service = PurchaseOrderService(db_session)
    first = service.execute_agent_run(run.id)
    db_session.commit()
    second = service.execute_agent_run(run.id)
    db_session.commit()

    assert first.id == second.id


def test_split_execution_creates_two_idempotent_orders(db_session, scenario_one):
    run, approvals = _approved_split_run(db_session, scenario_one)

    service = PurchaseOrderService(db_session)
    first = service.execute_agent_run_orders(run.id)
    db_session.commit()
    second = service.execute_agent_run_orders(run.id)
    db_session.commit()

    assert len(first) == 2
    assert [order.id for order in first] == [order.id for order in second]
    assert {order.supplier_id for order in first} == {approval.proposed_action_json["supplier_id"] for approval in approvals}
    assert all(order.status == "VALIDATED" for order in first)


def test_individual_approval_execution_does_not_require_other_approval(db_session, scenario_one):
    _run, approvals = _pending_split_run(db_session, scenario_one)
    service = PurchaseOrderService(db_session)
    ApprovalService(db_session).approve(approvals[0].id, "buyer@example.com")
    db_session.commit()

    first = service.execute_approval(approvals[0].id)
    db_session.commit()
    second = service.execute_approval(approvals[0].id)
    db_session.commit()

    db_session.refresh(approvals[0])
    db_session.refresh(approvals[1])
    assert first.id == second.id
    assert approvals[0].proposed_action_json["purchase_order_id"] == first.id
    assert approvals[0].proposed_action_json["execution_status"] == "VALIDATED"
    assert approvals[1].status == "PENDING"
    assert approvals[1].proposed_action_json.get("purchase_order_id") is None


def test_pending_or_rejected_approval_cannot_execute(db_session, scenario_one):
    _run, approvals = _pending_split_run(db_session, scenario_one)
    service = PurchaseOrderService(db_session)

    for approval in approvals[:1]:
        try:
            service.execute_approval(approval.id)
        except Exception as exc:
            assert "approved" in str(exc).lower()
        else:
            raise AssertionError("Pending approval should not execute")

    ApprovalService(db_session).reject(approvals[1].id, "buyer@example.com")
    db_session.commit()
    try:
        service.execute_approval(approvals[1].id)
    except Exception as exc:
        assert "approved" in str(exc).lower()
    else:
        raise AssertionError("Rejected approval should not execute")


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
    recovery_case = db_session.query(PurchaseOrderRecoveryCase).one()
    assert recovery_case.purchase_order_id == order.id
    assert recovery_case.shortfall_quantity == 400

