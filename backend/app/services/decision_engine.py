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
        decision, actions = self.decide_actions_for_recommendation(recommendation_id)
        return decision, actions[0] if actions else None

    def decide_actions_for_recommendation(self, recommendation_id: int) -> tuple[PurchasingDecision, list[ProposedAction]]:
        recommendation = self.repo.get_recommendation(recommendation_id)
        if not recommendation:
            raise NotFoundError("Recommendation not found")
        requirement = self.inventory_service.calculate_purchase_requirement(
            recommendation.product_id,
            recommendation.warehouse_id,
            self.settings.planning_horizon_days,
        )
        suppliers = self.supplier_service.list_options(recommendation.product_id)
        product = recommendation.product
        warehouse = recommendation.warehouse
        evidence = [
            f"Product {product.sku} {product.name} (id {product.id}) in warehouse {warehouse.name} (id {warehouse.id})",
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
                [],
            )

        supplier_failure_evidence: list[str] = []
        supplier_risks: list[str] = []
        for index, supplier in enumerate(suppliers):
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
                decision, proposed = self._single_action(recommendation, supplier, proposed_quantity)
                total = proposed.total_amount
                return (
                    PurchasingDecision(
                        decision=decision,
                        original_quantity=recommendation.recommended_quantity,
                        proposed_quantity=proposed_quantity,
                        supplier_id=supplier.supplier_id,
                        reasoning=f"Recommendation should be {decision.lower()} because deterministic replenishment requires {requirement.required_quantity} units and supplier {supplier.supplier_name} (id {supplier.supplier_id}) satisfies all constraints.",
                        evidence=evidence + [f"Supplier {supplier.supplier_name} (id {supplier.supplier_id}) can deliver {proposed_quantity} units at {supplier.unit_price} per unit"],
                        risks=[],
                        missing_information=[],
                        requires_approval=total > self.settings.purchase_auto_approval_limit,
                        confidence="HIGH",
                        constraint_result=constraint_result,
                    ),
                    [proposed],
                )

            split_actions = self._try_split_plan(recommendation, requirement, suppliers, index, supplier)
            if split_actions:
                total_quantity = sum(action.quantity for action in split_actions)
                total_cost = money(sum((action.total_amount for action in split_actions), Decimal("0")))
                supplier_descriptions = [
                    f"{action.supplier_name} (id {action.supplier_id}) supplies {action.quantity} units"
                    for action in split_actions
                ]
                return (
                    PurchasingDecision(
                        decision="ACCEPT" if total_quantity == recommendation.recommended_quantity else "MODIFY",
                        original_quantity=recommendation.recommended_quantity,
                        proposed_quantity=total_quantity,
                        supplier_id=None,
                        reasoning=(
                            f"Recommendation should be split because supplier {supplier.supplier_name} "
                            f"(id {supplier.supplier_id}) cannot fulfill the full {requirement.required_quantity} units, "
                            f"but can supply a feasible partial quantity."
                        ),
                        evidence=evidence
                        + [
                            f"Split sourcing for product {product.sku} {product.name} (id {product.id}): "
                            + "; ".join(supplier_descriptions),
                            f"Total split quantity is {total_quantity}; total split cost is {total_cost}",
                        ],
                        risks=[],
                        missing_information=[],
                        requires_approval=True,
                        confidence="HIGH",
                    ),
                    split_actions,
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
            [],
        )

    def _single_action(self, recommendation, supplier, proposed_quantity: int) -> tuple[str, ProposedAction]:
        decision = "ACCEPT" if proposed_quantity == recommendation.recommended_quantity else "MODIFY"
        total = money(Decimal(proposed_quantity) * supplier.unit_price)
        return decision, self._action(recommendation, supplier, proposed_quantity, total, decision)

    def _try_split_plan(self, recommendation, requirement, suppliers, supplier_index: int, first_supplier) -> list[ProposedAction]:
        partial_quantity = self._partial_quantity(first_supplier.available_quantity, requirement.required_quantity, first_supplier.order_multiple)
        if partial_quantity < first_supplier.minimum_order_quantity:
            return []
        first_constraint = self.constraint_engine.evaluate(
            recommendation.product_id,
            recommendation.warehouse_id,
            first_supplier.supplier_id,
            partial_quantity,
            requirement.required_by_date,
        )
        if not first_constraint.valid:
            return []

        remaining_quantity = max(0, requirement.required_quantity - partial_quantity)
        if remaining_quantity <= 0:
            return []

        for supplier in suppliers[supplier_index + 1 :]:
            proposed_quantity = max(remaining_quantity, supplier.minimum_order_quantity)
            proposed_quantity = round_up_to_multiple(proposed_quantity, supplier.order_multiple)
            constraint_result = self.constraint_engine.evaluate(
                recommendation.product_id,
                recommendation.warehouse_id,
                supplier.supplier_id,
                proposed_quantity,
                requirement.required_by_date,
            )
            if constraint_result.valid:
                first_total = money(Decimal(partial_quantity) * first_supplier.unit_price)
                second_total = money(Decimal(proposed_quantity) * supplier.unit_price)
                return [
                    self._action(recommendation, first_supplier, partial_quantity, first_total, "MODIFY"),
                    self._action(recommendation, supplier, proposed_quantity, second_total, "MODIFY"),
                ]
        return []

    @staticmethod
    def _partial_quantity(available_quantity: int, required_quantity: int, order_multiple: int) -> int:
        quantity = min(available_quantity, required_quantity)
        if order_multiple > 1:
            quantity -= quantity % order_multiple
        return max(0, quantity)

    @staticmethod
    def _action(recommendation, supplier, quantity: int, total: Decimal, decision: str) -> ProposedAction:
        return ProposedAction(
            recommendation_id=recommendation.id,
            product_id=recommendation.product_id,
            product_sku=recommendation.product.sku,
            product_name=recommendation.product.name,
            warehouse_id=recommendation.warehouse_id,
            warehouse_name=recommendation.warehouse.name,
            supplier_id=supplier.supplier_id,
            supplier_name=supplier.supplier_name,
            quantity=quantity,
            unit_price=supplier.unit_price,
            total_amount=total,
            expected_delivery_date=date.today() + timedelta(days=supplier.lead_time_days),
            decision=decision,
        )

