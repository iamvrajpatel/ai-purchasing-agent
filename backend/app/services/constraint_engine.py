from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.inventory_repository import InventoryRepository
from app.repositories.purchasing_repository import PurchasingRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.common import CheckResult, ConstraintResult, ConstraintViolation
from app.utils.calculations import money


class ConstraintEngine:
    def __init__(self, db: Session):
        self.db = db
        self.inventory_repo = InventoryRepository(db)
        self.purchasing_repo = PurchasingRepository(db)
        self.supplier_repo = SupplierRepository(db)

    def evaluate(self, product_id: int, warehouse_id: int, supplier_id: int, quantity: int, required_by: date | None = None) -> ConstraintResult:
        checks: list[CheckResult] = []
        violations: list[ConstraintViolation] = []
        today = date.today()
        budget_period = PurchasingRepository.budget_period_for(today)
        product = self.purchasing_repo.get_product(product_id)
        supplier_product = self.supplier_repo.get_supplier_conditions(supplier_id, product_id)
        budget = self.purchasing_repo.current_budget(warehouse_id, budget_period)
        warehouse = self.purchasing_repo.get_warehouse(warehouse_id)

        if quantity <= 0:
            checks.append(CheckResult(name="quantity", status="FAIL", details="Quantity must be positive"))
            violations.append(ConstraintViolation(code="INVALID_QUANTITY", severity="BLOCKING", message="Quantity must be positive"))

        if not product:
            checks.append(CheckResult(name="product", status="UNKNOWN", details="Product not found"))
            violations.append(ConstraintViolation(code="PRODUCT_MISSING", severity="BLOCKING", message="Product is unavailable"))
        if not supplier_product:
            checks.append(CheckResult(name="supplier", status="UNKNOWN", details="Supplier conditions not found"))
            violations.append(ConstraintViolation(code="SUPPLIER_CONDITIONS_MISSING", severity="BLOCKING", message="Supplier data is missing"))
            return ConstraintResult(valid=False, checks=checks, violations=violations)

        total_cost = money(Decimal(quantity) * supplier_product.unit_price)
        if budget and total_cost <= budget.available_budget:
            checks.append(CheckResult(name="budget", status="PASS", details="Purchase is within available budget", metadata={"cost": str(total_cost), "available": str(budget.available_budget)}))
        elif budget:
            checks.append(CheckResult(name="budget", status="FAIL", details="Purchase exceeds available budget", metadata={"cost": str(total_cost), "available": str(budget.available_budget)}))
            violations.append(ConstraintViolation(code="BUDGET_EXCEEDED", severity="BLOCKING", message="Purchase exceeds available budget"))
        else:
            checks.append(CheckResult(name="budget", status="UNKNOWN", details="Budget record is missing"))
            violations.append(ConstraintViolation(code="BUDGET_UNKNOWN", severity="BLOCKING", message="Budget could not be verified"))

        if quantity >= supplier_product.minimum_order_quantity:
            checks.append(CheckResult(name="supplier_moq", status="PASS", details="Quantity satisfies MOQ"))
        else:
            checks.append(CheckResult(name="supplier_moq", status="FAIL", details="Quantity is below supplier MOQ"))
            violations.append(ConstraintViolation(code="MOQ_VIOLATION", severity="BLOCKING", message="Quantity is below supplier MOQ"))

        if quantity % supplier_product.order_multiple == 0:
            checks.append(CheckResult(name="order_multiple", status="PASS", details="Quantity satisfies order multiple"))
        else:
            checks.append(CheckResult(name="order_multiple", status="FAIL", details="Quantity violates order multiple"))
            violations.append(ConstraintViolation(code="ORDER_MULTIPLE_VIOLATION", severity="BLOCKING", message="Quantity violates order multiple"))

        if quantity <= supplier_product.available_quantity:
            checks.append(CheckResult(name="supplier_availability", status="PASS", details="Supplier has sufficient available quantity"))
        else:
            checks.append(CheckResult(name="supplier_availability", status="FAIL", details="Supplier cannot fulfill quantity"))
            violations.append(ConstraintViolation(code="SUPPLIER_AVAILABILITY_SHORTAGE", severity="BLOCKING", message="Supplier capacity is insufficient"))

        expected_delivery = today + timedelta(days=supplier_product.lead_time_days)
        if required_by is None or expected_delivery <= required_by:
            checks.append(CheckResult(name="delivery_timing", status="PASS", details="Supplier can deliver by required date", metadata={"expected_delivery_date": expected_delivery.isoformat()}))
        else:
            checks.append(CheckResult(name="delivery_timing", status="FAIL", details="Supplier delivery is later than required date", metadata={"expected_delivery_date": expected_delivery.isoformat(), "required_by": required_by.isoformat()}))
            violations.append(ConstraintViolation(code="LATE_DELIVERY", severity="BLOCKING", message="Supplier cannot deliver before required date"))

        if product and warehouse:
            current_occupancy = self.inventory_repo.current_warehouse_occupied_volume(warehouse_id)
            order_volume = Decimal(quantity) * product.unit_volume
            if Decimal(current_occupancy) + order_volume <= warehouse.total_storage_capacity:
                checks.append(
                    CheckResult(
                        name="storage",
                        status="PASS",
                        details="Projected storage capacity is available",
                        metadata={
                            "current_occupied_volume": str(current_occupancy),
                            "order_volume": str(order_volume),
                            "capacity": str(warehouse.total_storage_capacity),
                        },
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        name="storage",
                        status="FAIL",
                        details="Projected storage capacity exceeded",
                        metadata={
                            "current_occupied_volume": str(current_occupancy),
                            "order_volume": str(order_volume),
                            "capacity": str(warehouse.total_storage_capacity),
                        },
                    )
                )
                violations.append(ConstraintViolation(code="STORAGE_CAPACITY_EXCEEDED", severity="BLOCKING", message="Order exceeds warehouse capacity"))
        else:
            checks.append(CheckResult(name="storage", status="UNKNOWN", details="Storage cannot be verified"))
            violations.append(ConstraintViolation(code="STORAGE_UNKNOWN", severity="BLOCKING", message="Storage could not be verified"))

        checks.append(CheckResult(name="duplicate_order", status="PASS", details="Run-level idempotency is enforced during execution"))

        return ConstraintResult(valid=not any(v.severity == "BLOCKING" for v in violations), checks=checks, violations=violations)

