# Evaluation

| Scenario | Expected result | Evidence |
| --- | --- | --- |
| Scenario 1 SKU-101 | `MODIFY` 800 to 650 | 900 demand + 100 safety - 200 sellable - 150 incoming |
| Budget restriction | Block execution | Constraint engine returns `BUDGET_EXCEEDED` |
| MOQ violation | Investigate or alternative supplier | Constraint engine returns `MOQ_VIOLATION` |
| Storage shortage | Block execution | Constraint engine returns `STORAGE_CAPACITY_EXCEEDED` |
| Partial fulfillment | Validation failure and escalation | Supplier outcome validation checks confirmed quantity |
| Duplicate execution | Single purchase order | Idempotency key per agent run |

