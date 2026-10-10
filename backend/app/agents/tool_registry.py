from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.tools.forecast_tools import ForecastTools
from app.tools.inventory_tools import InventoryTools
from app.tools.purchasing_tools import PurchasingTools
from app.tools.recovery_tools import RecoveryTools
from app.tools.supplier_tools import SupplierTools


class ToolRegistry:
    def __init__(self, db: Session):
        inventory = InventoryTools(db)
        forecast = ForecastTools(db)
        supplier = SupplierTools(db)
        purchasing = PurchasingTools(db)
        recovery = RecoveryTools(db)
        self._tools: dict[str, Callable[..., dict]] = {
            "get_product_details": purchasing.get_product_details,
            "get_inventory": inventory.get_inventory,
            "get_demand_forecast": forecast.get_demand_forecast,
            "get_sales_history": forecast.get_sales_history,
            "get_open_purchase_orders": purchasing.get_open_purchase_orders,
            "get_supplier_options": supplier.get_supplier_options,
            "get_supplier_conditions": supplier.get_supplier_conditions,
            "get_available_budget": purchasing.get_available_budget,
            "get_storage_capacity": inventory.get_storage_capacity,
            "calculate_purchase_requirement": inventory.calculate_purchase_requirement,
            "evaluate_purchase_constraints": purchasing.evaluate_purchase_constraints,
            "get_purchase_order_details": recovery.get_purchase_order_details,
            "get_supplier_confirmation_outcome": recovery.get_supplier_confirmation_outcome,
            "calculate_remaining_shortfall": recovery.calculate_remaining_shortfall,
            "list_alternate_suppliers": recovery.list_alternate_suppliers,
            "calculate_current_requirement_after_confirmation": recovery.calculate_current_requirement_after_confirmation,
        }
        self._required_args: dict[str, list[str]] = {
            "get_product_details": ["product_id"],
            "get_inventory": ["product_id", "warehouse_id"],
            "get_demand_forecast": ["product_id", "warehouse_id", "start_date", "end_date"],
            "get_sales_history": ["product_id", "warehouse_id", "start_date", "end_date"],
            "get_open_purchase_orders": ["product_id", "warehouse_id"],
            "get_supplier_options": ["product_id"],
            "get_supplier_conditions": ["supplier_id", "product_id"],
            "get_available_budget": ["warehouse_id"],
            "get_storage_capacity": ["warehouse_id"],
            "calculate_purchase_requirement": ["product_id", "warehouse_id", "planning_horizon_days"],
            "evaluate_purchase_constraints": ["product_id", "warehouse_id", "supplier_id", "quantity"],
            "get_purchase_order_details": ["purchase_order_id"],
            "get_supplier_confirmation_outcome": ["purchase_order_id"],
            "calculate_remaining_shortfall": ["purchase_order_id"],
            "list_alternate_suppliers": ["purchase_order_id"],
            "calculate_current_requirement_after_confirmation": ["purchase_order_id"],
        }
        self._properties: dict[str, dict[str, dict[str, str]]] = {
            "get_product_details": {"product_id": {"type": "integer"}},
            "get_inventory": {"product_id": {"type": "integer"}, "warehouse_id": {"type": "integer"}},
            "get_demand_forecast": {
                "product_id": {"type": "integer"},
                "warehouse_id": {"type": "integer"},
                "start_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
            },
            "get_sales_history": {
                "product_id": {"type": "integer"},
                "warehouse_id": {"type": "integer"},
                "start_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
            },
            "get_open_purchase_orders": {"product_id": {"type": "integer"}, "warehouse_id": {"type": "integer"}},
            "get_supplier_options": {"product_id": {"type": "integer"}},
            "get_supplier_conditions": {"supplier_id": {"type": "integer"}, "product_id": {"type": "integer"}},
            "get_available_budget": {"warehouse_id": {"type": "integer"}},
            "get_storage_capacity": {"warehouse_id": {"type": "integer"}},
            "calculate_purchase_requirement": {
                "product_id": {"type": "integer"},
                "warehouse_id": {"type": "integer"},
                "planning_horizon_days": {"type": "integer"},
            },
            "evaluate_purchase_constraints": {
                "product_id": {"type": "integer"},
                "warehouse_id": {"type": "integer"},
                "supplier_id": {"type": "integer"},
                "quantity": {"type": "integer"},
            },
            "get_purchase_order_details": {"purchase_order_id": {"type": "integer"}},
            "get_supplier_confirmation_outcome": {"purchase_order_id": {"type": "integer"}},
            "calculate_remaining_shortfall": {"purchase_order_id": {"type": "integer"}},
            "list_alternate_suppliers": {
                "purchase_order_id": {"type": "integer"},
                "exclude_original_supplier": {"type": "boolean"},
            },
            "calculate_current_requirement_after_confirmation": {"purchase_order_id": {"type": "integer"}},
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> dict:
        if name not in self._tools:
            raise ValueError(f"Unknown tool {name}")
        return self._tools[name](**self.filter_arguments(name, arguments))

    def filter_arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Unknown tool {name}")
        allowed = set(self._properties[name])
        return {key: value for key, value in arguments.items() if key in allowed}

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Restricted purchasing tool: {name}",
                    "parameters": {
                        "type": "object",
                        "properties": self._properties[name],
                        "required": self._required_args[name],
                        "additionalProperties": False,
                    },
                },
            }
            for name in self._tools
        ]

