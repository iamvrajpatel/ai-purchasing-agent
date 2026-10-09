import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.agent_prompts import FINAL_DECISION_INSTRUCTIONS, SYSTEM_PROMPT
from app.agents.llm_client import DirectOpenAIClient, parse_json_object
from app.agents.tool_executor import ToolExecutor
from app.agents.tool_registry import ToolRegistry
from app.core.config import get_settings
from app.models import AgentEvent, AgentRun
from app.repositories.purchasing_repository import PurchasingRepository
from app.schemas.purchasing import PurchasingDecision
from app.services.approval_service import ApprovalService
from app.services.decision_engine import DecisionEngine
from app.services.validation_service import ValidationService
from app.utils.exceptions import NotFoundError


class PurchasingAgent:
    def __init__(self, db: Session, llm_client: DirectOpenAIClient | None = None):
        self.db = db
        self.settings = get_settings()
        self.repo = PurchasingRepository(db)
        self.llm_client = llm_client

    async def analyze(self, recommendation_id: int) -> AgentRun:
        recommendation = self.repo.get_recommendation(recommendation_id)
        if not recommendation:
            raise NotFoundError("Recommendation not found")
        run = AgentRun(
            recommendation_id=recommendation_id,
            status="CREATED",
            original_quantity=recommendation.recommended_quantity,
            model_name=self.settings.openai_model,
        )
        self.db.add(run)
        self.db.flush()
        try:
            run.status = "INVESTIGATING"
            self._event(run.id, "STARTED", "Agent investigation started", {"recommendation_id": recommendation_id})
            client = self.llm_client or DirectOpenAIClient()
            executor = ToolExecutor(self.db, run.id)
            registry = ToolRegistry(self.db)
            messages: list[dict] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Analyze recommendation {recommendation.id}: product_id={recommendation.product_id}, "
                        f"warehouse_id={recommendation.warehouse_id}, recommended_quantity={recommendation.recommended_quantity}. "
                        f"{FINAL_DECISION_INSTRUCTIONS}"
                    ),
                },
            ]
            for _ in range(self.settings.agent_max_tool_calls):
                message = await client.chat(messages, tools=registry.schemas())
                messages.append(message)
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    break
                for call in tool_calls:
                    function = call["function"]
                    output = executor.execute(function["name"], function.get("arguments") or "{}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": function["name"],
                            "content": json.dumps(output),
                        }
                    )
                    self._event(run.id, "TOOL_COMPLETED", f"{function['name']} completed", output)

            if executor.call_count == 0:
                raise RuntimeError("Agent did not call any operational tools; investigation is required before deciding")

            final = await client.chat(messages + [{"role": "user", "content": FINAL_DECISION_INSTRUCTIONS}], tools=None)
            llm_decision = PurchasingDecision.model_validate(parse_json_object(final.get("content") or "{}"))
            deterministic_decision, proposed_action = DecisionEngine(self.db).decide_for_recommendation(recommendation_id)
            final_decision = self._validated_decision(llm_decision, deterministic_decision)
            run.status = "DECIDED"
            run.decision = final_decision.decision
            run.proposed_quantity = final_decision.proposed_quantity
            run.proposed_supplier_id = final_decision.supplier_id
            run.reasoning = final_decision.reasoning
            run.evidence_snapshot = {
                "llm_decision": llm_decision.model_dump(mode="json"),
                "server_validated_decision": final_decision.model_dump(mode="json"),
                "proposed_action": proposed_action.model_dump(mode="json") if proposed_action else None,
            }
            ValidationService(self.db).validate_decision(run.id, final_decision, proposed_action)
            if proposed_action:
                ApprovalService(self.db).ensure_approval_path(run.id, proposed_action, final_decision.requires_approval)
                run.status = "AWAITING_APPROVAL" if final_decision.requires_approval else "PROPOSED"
            elif final_decision.decision == "REJECT":
                run.status = "REJECTED"
            else:
                run.status = "INVESTIGATION_REQUIRED"
            run.completed_at = datetime.now(timezone.utc)
            self._event(run.id, "DECISION", f"Decision {run.decision}", run.evidence_snapshot)
        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            self._event(run.id, "FAILED", str(exc), {"type": exc.__class__.__name__})
        return run

    @staticmethod
    def _validated_decision(llm_decision: PurchasingDecision, deterministic_decision: PurchasingDecision) -> PurchasingDecision:
        if llm_decision.decision != deterministic_decision.decision:
            deterministic_decision.risks.append("LLM proposal was server-corrected after deterministic validation")
        return deterministic_decision

    def _event(self, run_id: int, event_type: str, message: str, metadata: dict | None = None) -> None:
        self.db.add(AgentEvent(agent_run_id=run_id, event_type=event_type, message=message, metadata_json=metadata))
        self.db.flush()

