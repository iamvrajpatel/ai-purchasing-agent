from datetime import date

from app.api.routes.dashboard import summary
from app.models import AgentRun, ApprovalRequest


def test_dashboard_returns_budget_health_and_pending_exposure(db_session, scenario_one):
    run = AgentRun(
        recommendation_id=scenario_one["recommendation"].id,
        status="AWAITING_APPROVAL",
        decision="MODIFY",
        original_quantity=800,
        proposed_quantity=650,
        reasoning="test",
        evidence_snapshot={},
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        ApprovalRequest(
            agent_run_id=run.id,
            status="PENDING",
            proposed_action_json={
                "product_id": scenario_one["product"].id,
                "product_sku": scenario_one["product"].sku,
                "product_name": scenario_one["product"].name,
                "warehouse_id": scenario_one["warehouse"].id,
                "warehouse_name": scenario_one["warehouse"].name,
                "supplier_id": scenario_one["supplier"].id,
                "supplier_name": scenario_one["supplier"].name,
                "quantity": 100,
                "unit_price": "50.00",
                "total_amount": "5000.00",
                "expected_delivery_date": date.today().isoformat(),
                "decision": "MODIFY",
            },
        )
    )
    db_session.commit()

    result = summary(db_session)

    assert result.budgets
    assert result.budgets[0]["available_budget"] == "35000.00"
    assert result.pending_approval_exposure
    assert result.pending_approval_exposure[0]["pending_total"] == "5000.00"
    assert result.pending_approval_exposure[0]["pending_count"] == 1
