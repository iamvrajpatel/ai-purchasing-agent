from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.purchasing_repository import PurchasingRepository
from app.services.constraint_engine import ConstraintEngine
from app.services.decision_engine import DecisionEngine
from app.services.inventory_service import InventoryService
from app.services.supplier_service import SupplierService
from app.utils.calculations import round_up_to_multiple


def _safe_database_url() -> str:
    value = get_settings().database_url
    if "@" not in value:
        return value
    prefix, rest = value.split("@", 1)
    if ":" not in prefix:
        return value
    return prefix.rsplit(":", 1)[0] + ":***@" + rest


def diagnose_recommendations() -> None:
    db = SessionLocal()
    try:
        repo = PurchasingRepository(db)
        inventory = InventoryService(db)
        suppliers = SupplierService(db)
        constraints = ConstraintEngine(db)
        decisions = DecisionEngine(db)
        settings = get_settings()
        for recommendation in repo.list_recommendations():
            print(f"\nRecommendation #{recommendation.id}: {recommendation.product.sku} {recommendation.product.name}")
            requirement = inventory.calculate_purchase_requirement(
                recommendation.product_id,
                recommendation.warehouse_id,
                settings.planning_horizon_days,
            )
            print(
                f"  recommended={recommendation.recommended_quantity}, "
                f"required={requirement.required_quantity}, required_by={requirement.required_by_date}"
            )
            options = suppliers.list_options(recommendation.product_id)
            if not options:
                print("  supplier options: none")
            for option in options:
                quantity = max(requirement.required_quantity, option.minimum_order_quantity)
                quantity = round_up_to_multiple(quantity, option.order_multiple)
                result = constraints.evaluate(
                    recommendation.product_id,
                    recommendation.warehouse_id,
                    option.supplier_id,
                    quantity,
                    requirement.required_by_date,
                )
                failed = [f"{check.name}={check.status}" for check in result.checks if check.status != "PASS"]
                print(
                    f"  supplier={option.supplier_name}, quantity={quantity}, valid={result.valid}, "
                    f"failed={failed or 'none'}"
                )
            decision, actions = decisions.decide_actions_for_recommendation(recommendation.id)
            print(f"  decision={decision.decision}, proposed_quantity={decision.proposed_quantity}, risks={decision.risks}")
            for action in actions:
                print(
                    f"  action product={action.product_sku} {action.product_name} (id={action.product_id}), "
                    f"supplier={action.supplier_name} (id={action.supplier_id}), "
                    f"quantity={action.quantity}, total={action.total_amount}"
                )
    except OperationalError as exc:
        print("Could not connect to PostgreSQL.")
        print(f"Configured DATABASE_URL: {_safe_database_url()}")
        raise SystemExit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    diagnose_recommendations()

