from datetime import date, timedelta
from decimal import Decimal

from app.models import Inventory, PurchaseOrder, PurchaseOrderItem, Supplier, SupplierProduct
from app.services.purchase_order_recovery_service import PurchaseOrderRecoveryService


def _partial_order(db_session, scenario_one, requested=500, confirmed=250, supplier=None):
    supplier = supplier or scenario_one["supplier"]
    total = Decimal(requested) * Decimal("50")
    order = PurchaseOrder(
        supplier_id=supplier.id,
        warehouse_id=scenario_one["warehouse"].id,
        status="VALIDATION_FAILED",
        supplier_confirmation_status="PARTIALLY_CONFIRMED",
        supplier_response_json={"status": "PARTIALLY_CONFIRMED", "requested_quantity": requested, "confirmed_quantity": confirmed},
        expected_delivery_date=date.today() + timedelta(days=1),
        total_amount=total,
        source_recommendation_id=scenario_one["recommendation"].id,
        idempotency_key=f"partial-{requested}-{confirmed}-{supplier.id}",
    )
    order.items.append(
        PurchaseOrderItem(
            product_id=scenario_one["product"].id,
            quantity=requested,
            unit_price=Decimal("50"),
            line_total=total,
        )
    )
    db_session.add(order)
    db_session.commit()
    return order


def _alternate_supplier(db_session, scenario_one, name="Backup Supplier", price=Decimal("51.00"), available=500):
    supplier = Supplier(name=name, contact_email=f"{name.lower().replace(' ', '-')}@example.com", status="ACTIVE", reliability_score=Decimal("0.920"))
    db_session.add(supplier)
    db_session.flush()
    db_session.add(
        SupplierProduct(
            supplier_id=supplier.id,
            product_id=scenario_one["product"].id,
            unit_price=price,
            minimum_order_quantity=100,
            order_multiple=50,
            lead_time_days=1,
            available_quantity=available,
            active=True,
        )
    )
    db_session.commit()
    return supplier


def test_partial_confirmation_calculates_shortfall(db_session, scenario_one):
    _alternate_supplier(db_session, scenario_one)
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)

    recovery_case = PurchaseOrderRecoveryService(db_session).analyze_purchase_order(order.id)

    assert recovery_case.requested_quantity == 500
    assert recovery_case.confirmed_quantity == 250
    assert recovery_case.shortfall_quantity == 250


def test_recovery_sources_remainder_from_alternate_supplier(db_session, scenario_one):
    alternate = _alternate_supplier(db_session, scenario_one)
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)

    recovery_case = PurchaseOrderRecoveryService(db_session).analyze_purchase_order(order.id)

    assert recovery_case.decision == "SOURCE_REMAINDER"
    assert recovery_case.status == "PENDING_APPROVAL"
    assert recovery_case.proposed_action_json["supplier_id"] == alternate.id
    assert recovery_case.proposed_action_json["quantity"] == 250


def test_original_supplier_is_excluded_from_recovery_sourcing(db_session, scenario_one):
    alternate = _alternate_supplier(db_session, scenario_one, price=Decimal("60.00"))
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)

    recovery_case = PurchaseOrderRecoveryService(db_session).analyze_purchase_order(order.id)

    assert recovery_case.proposed_action_json["supplier_id"] == alternate.id
    assert recovery_case.proposed_action_json["supplier_id"] != order.supplier_id


def test_recovery_returns_no_action_when_confirmed_quantity_covers_requirement(db_session, scenario_one):
    inventory = db_session.query(Inventory).one()
    inventory.on_hand_quantity = 2000
    db_session.commit()
    _alternate_supplier(db_session, scenario_one)
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)

    recovery_case = PurchaseOrderRecoveryService(db_session).analyze_purchase_order(order.id)

    assert recovery_case.decision == "NO_ACTION_REQUIRED"
    assert recovery_case.status == "RESOLVED"
    assert recovery_case.proposed_action_json is None


def test_recovery_escalates_when_no_alternate_supplier_is_feasible(db_session, scenario_one):
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)

    recovery_case = PurchaseOrderRecoveryService(db_session).analyze_purchase_order(order.id)

    assert recovery_case.decision == "ESCALATE"
    assert recovery_case.status == "ESCALATED"
    assert recovery_case.proposed_action_json is None
    assert "No feasible alternate supplier found" in recovery_case.risks_json


def test_approved_recovery_execution_creates_one_supplemental_order(db_session, scenario_one):
    _alternate_supplier(db_session, scenario_one)
    order = _partial_order(db_session, scenario_one, requested=500, confirmed=250)
    service = PurchaseOrderRecoveryService(db_session)
    recovery_case = service.analyze_purchase_order(order.id)
    db_session.commit()

    service.approve(recovery_case.id, "buyer@example.com")
    db_session.commit()
    first = service.execute(recovery_case.id)
    db_session.commit()
    second = service.execute(recovery_case.id)
    db_session.commit()

    assert first.id == second.id
    assert first.id != order.id
    assert recovery_case.supplemental_purchase_order_id == first.id
