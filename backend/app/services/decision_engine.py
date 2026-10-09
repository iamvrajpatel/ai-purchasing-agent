from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.purchasing_repository import PurchasingRepository
from app.services.constraint_engine import ConstraintEngine
from app.services.inventory_service import InventoryService
from app.services.supplier_service import SupplierService
from app.schemas.purchasing import ProposedAction, PurchasingDecision
from app.utils.calculations import money, round_up_to_multiple
from app.utils.exceptions import NotFoundError


class DecisionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.inventory_service = InventoryService(db)
        self.supplier_service = SupplierService(db)
        self.constraint_engine = ConstraintEngine(db)
        self.repo = PurchasingRepository(db)

    def decide_for_recommendation(self, recommendation_id: int) -> tuple[PurchasingDecision, ProposedAction | None]:
        recommendation = self.repo.get_recommendation(recommendation_id)
        if not recommendation:
            raise NotFoundError("Recommendation not found")
        requirement = self.inventory_service.calculate_purchase_requirement(
            recommendation.product_id,
            recommendation.warehouse_id,
            self.settings.planning_horizon_days,
        )
        suppliers = self.supplier_service.list_options(recommendation.product_id)
        evidence = [
            f"Sellable inventory is {requirement.sellable_inventory}",
            f"Forecast demand is {requirement.forecast_demand}",
            f"Timely incoming quantity is {requirement.timely_incoming_quantity}",
            f"Safety stock target is {requirement.safety_stock}",
            f"Calculated requirement is {requirement.required_quantity}",
        ]

        if requirement.required_quantity == 0:
            return (
                PurchasingDecision(
                    decision="REJECT",
                    original_quantity=recommendation.recommended_quantity,
                    proposed_quantity=None,
                    supplier_id=None,
                    reasoning="No purchase is needed because sellable inventory and timely incoming stock cover demand plus safety stock.",
                    evidence=evidence,
                    risks=[],
                    missing_information=[],
                    requires_approval=False,
                    confidence="HIGH",
                ),
                None,
            )

        supplier_failure_evidence: list[str] = []
        supplier_risks: list[str] = []
        for supplier in suppliers:
            proposed_quantity = max(requirement.required_quantity, supplier.minimum_order_quantity)
            proposed_quantity = round_up_to_multiple(proposed_quantity, supplier.order_multiple)
            constraint_result = self.constraint_engine.evaluate(
                recommendation.product_id,
                recommendation.warehouse_id,
                supplier.supplier_id,
                proposed_quantity,
                requirement.required_by_date,
            )
            if constraint_result.valid:
                decision = "ACCEPT" if proposed_quantity == recommendation.recommended_quantity else "MODIFY"
                total = money(Decimal(proposed_quantity) * supplier.unit_price)
                proposed = ProposedAction(
                    recommendation_id=recommendation.id,
                    product_id=recommendation.product_id,
                    warehouse_id=recommendation.warehouse_id,
                    supplier_id=supplier.supplier_id,
                    quantity=proposed_quantity,
                    unit_price=supplier.unit_price,
                    total_amount=total,
                    expected_delivery_date=date.today() + timedelta(days=supplier.lead_time_days),
                    decision=decision,
                )
                return (
                    PurchasingDecision(
                        decision=decision,
                        original_quantity=recommendation.recommended_quantity,
                        proposed_quantity=proposed_quantity,
                        supplier_id=supplier.supplier_id,
                        reasoning=f"Recommendation should be {decision.lower()} because deterministic replenishment requires {requirement.required_quantity} units and selected supplier constraints are satisfied.",
                        evidence=evidence + [f"Supplier {supplier.supplier_name} can deliver {proposed_quantity} units at {supplier.unit_price} per unit"],
                        risks=[],
                        missing_information=[],
                        requires_approval=total > self.settings.purchase_auto_approval_limit,
                        confidence="HIGH",
                        constraint_result=constraint_result,
                    ),
                    proposed,
                )
            failed_checks = [check for check in constraint_result.checks if check.status in {"FAIL", "UNKNOWN"}]
            if failed_checks:
                details = "; ".join(f"{check.name}: {check.details}" for check in failed_checks)
                supplier_failure_evidence.append(
                    f"Supplier {supplier.supplier_name} failed for {proposed_quantity} units: {details}"
                )
                supplier_risks.extend(f"{supplier.supplier_name}: {violation.code}" for violation in constraint_result.violations)

        if not suppliers:
            supplier_failure_evidence.append("No active supplier catalog rows were found for this product")
            supplier_risks.append("SUPPLIER_OPTIONS_MISSING")

        return (
            PurchasingDecision(
                decision="INVESTIGATE",
                original_quantity=recommendation.recommended_quantity,
                proposed_quantity=None,
                supplier_id=None,
                reasoning="A purchase appears necessary, but no supplier option passed all mandatory constraints.",
                evidence=evidence + supplier_failure_evidence,
                risks=["No feasible supplier found", *supplier_risks],
                missing_information=[],
                requires_approval=True,
                confidence="MEDIUM",
            ),
            None,
        )

