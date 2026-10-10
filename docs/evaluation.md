# Evaluation

The evaluation approach is intentionally small and focused. It combines deterministic unit/integration tests, seeded demo data, and diagnostic scripts to show whether the agent made an appropriate decision and whether the result was validated.

| Evaluation Question | Scenario/Test | Expected Result | How It Is Verified |
| --- | --- | --- | --- |
| Was the decision correct? | Scenario 1 `SKU-101` recommendation | Original recommendation `800` is corrected to calculated requirement `650` with decision `MODIFY`. | `tests/test_decision_engine.py` verifies the deterministic decision and expected cost. `python app/diagnose_recommendations.py` prints the requirement and action. |
| Was split sourcing correct? | Best supplier cannot fulfill the full requirement, but can fulfill a valid partial quantity | The recommendation is split into two supplier actions whose quantities sum to the requirement, with product and supplier labels. | `tests/test_decision_engine.py` verifies split quantities, supplier ids/names, product SKU/name, and decision evidence. |
| Did the agent obtain necessary information? | Recommendation analysis | Agent uses inventory, forecast, supplier, budget, storage, PO, and constraint evidence before proposing an action. | `agent_tool_calls` persists tool inputs/outputs. Agent timeline events are shown in the UI. `verify_demo_db.py` confirms required data exists. |
| Did it respect budget constraints? | Budget too low for proposed purchase | Decision or execution is blocked with proof that cost exceeds available budget. | `tests/test_constraint_engine.py` verifies `BUDGET_EXCEEDED` and proof text. Dashboard budget health shows total, committed, reserved, available, and pending exposure. |
| Did it respect supplier constraints? | Supplier availability, MOQ, and order multiple checks | Invalid supplier options fail and are not executed. | `tests/test_constraint_engine.py` and `tests/test_decision_engine.py` verify supplier feasibility and no-feasible-supplier investigation paths. |
| Did it respect storage constraints? | Warehouse capacity exceeded | Purchase is blocked with projected volume, capacity, and overage amount. | `tests/test_constraint_engine.py` verifies `STORAGE_CAPACITY_EXCEEDED` and proof text. |
| Did it respect delivery constraints? | Supplier expected delivery is after required-by date | Purchase is blocked with expected date, required date, and delayed day count. | `tests/test_constraint_engine.py` verifies `LATE_DELIVERY` and delayed-days proof. |
| Did it take the appropriate action? | Buyer approves one supplier proposal | Only that approval can be executed, and it creates one PO for that supplier action. | `tests/test_purchase_orders.py` verifies independent approval execution, PO creation, and PO identity. |
| Did it avoid duplicate orders? | Execute the same approval or run twice | Existing PO is returned instead of creating a duplicate. | `tests/test_purchase_orders.py` verifies idempotent execution for single-action and split-action flows. |
| Did it validate the persisted PO? | PO created after approval | PO supplier, warehouse, product, quantity, and total match the approved action. | `ValidationService.validate_purchase_order` records validation; `tests/test_purchase_orders.py` verifies execution flows. |
| Did it validate supplier outcome? | Supplier confirms fewer units than requested | PO is marked validation failed and a recovery case is created. | `tests/test_purchase_orders.py` and `tests/test_recovery_service.py` verify partial confirmation detection and recovery creation. |
| What happens when the initial action does not work? | Scenario 2 partial fulfillment | System calculates shortfall, evaluates alternate suppliers, and proposes supplemental sourcing or escalation. | `tests/test_recovery_service.py` verifies source remainder, no-action-required, escalation, and supplemental PO execution. |
| Does the dashboard expose operational risk? | Budget and pending approvals | Dashboard returns budget health and pending approval exposure by warehouse. | `tests/test_dashboard.py` verifies budget and exposure response data. |

Supporting commands:

```bash
python app/verify_demo_db.py
python app/diagnose_recommendations.py
python -m pytest
```

Current automated test coverage includes decision logic, constraint logic, purchase-order execution, recovery handling, dashboard budget exposure, tool registry behavior, and state-machine safeguards.
