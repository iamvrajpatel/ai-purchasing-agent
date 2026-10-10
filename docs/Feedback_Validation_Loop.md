# Feedback And Validation Loop

The system validates the result of an agent decision instead of assuming that a proposed purchase order succeeded. The feedback loop is:

```text
AI investigates recommendation
-> deterministic backend validates the decision
-> buyer approves the proposed action
-> backend revalidates current state
-> purchase order is created
-> supplier response is captured
-> purchase order and supplier outcome are validated
-> recovery or escalation is created when the outcome differs
```

| Feedback / Validation Step | Status | How Implemented |
| --- | --- | --- |
| AI investigates operational evidence | Implemented | `PurchasingAgent` uses restricted tools through `ToolRegistry` and `ToolExecutor`. Tool calls, outputs, and timeline events are persisted for review. |
| Backend validates the AI decision before action | Implemented | `DecisionEngine`, `ConstraintEngine`, and `ValidationService.validate_decision` recalculate the safe decision server-side before storing the proposal. |
| Buyer approves proposed action | Implemented | `ApprovalService` creates approval records. Split supplier proposals create separate approval rows, each with product/supplier/quantity/cost details. |
| Backend revalidates current state before execution | Implemented | `PurchaseOrderService` reruns constraints before creating a PO. Execution is blocked if budget, supplier availability, storage capacity, delivery timing, or other constraints changed after approval. |
| Purchase order is created idempotently | Implemented | Execution uses idempotency keys. Run-level execution and approval-level execution return existing POs on retry instead of creating duplicates. |
| Supplier response is captured | Implemented | The mock supplier adapter returns confirmation status, confirmed quantity, and external reference. These values are stored on `purchase_orders.supplier_response_json` and related PO fields. |
| Persisted PO is validated against the approved action | Implemented | `ValidationService.validate_purchase_order` checks supplier, warehouse, product, quantity, and total against the approved proposal. |
| Supplier outcome is validated | Implemented | `ValidationService.validate_supplier_outcome` checks supplier confirmation status and confirmed quantity. Partial confirmation, rejection, or mismatch creates validation failure. |
| Different outcome triggers recovery | Implemented | `RecoveryService` creates a recovery event and, for partial fulfillment, a `purchase_order_recovery_case`. `PurchaseOrderRecoveryService` calculates shortfall, evaluates alternatives, and can propose a supplemental PO. |
| Scenario 2 partial fulfillment is handled | Implemented | If a PO requested `500` units and the supplier confirms `250`, the system calculates a `250` shortfall, marks validation failed, creates a recovery case, and evaluates whether to source the remainder, take no action, or escalate. |
| Validation feedback is visible to the buyer | Implemented | PO detail shows validations and supplier status. Agent run pages show tool calls, events, decision evidence, and constraint proof. Dashboard shows budget health and pending approval exposure. |
