# Agent Workflow

1. Receive a recommendation ID.
2. Create an `agent_runs` record.
3. Let the LLM call only registered backend tools.
4. Persist each tool call and event.
5. Ask for a structured decision.
6. Recalculate the decision server-side with deterministic services.
7. Store the server-validated proposal.
8. Create an approval request when policy requires it.
9. Execute only through `PurchaseOrderService`.
10. Validate the persisted order and supplier outcome.

Missing `OPENAI_API_KEY` configuration is recorded as a failed agent run. Tests can inject a fake OpenAI client, but the app does not silently switch to a deterministic demo agent.

