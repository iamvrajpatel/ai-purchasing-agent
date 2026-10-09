import json
import time

from sqlalchemy.orm import Session

from app.agents.tool_registry import ToolRegistry
from app.models import AgentToolCall


class ToolExecutor:
    def __init__(self, db: Session, agent_run_id: int):
        self.db = db
        self.agent_run_id = agent_run_id
        self.registry = ToolRegistry(db)
        self.seen_calls: set[str] = set()
        self.call_count = 0

    def execute(self, tool_name: str, raw_arguments: str | dict) -> dict:
        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        signature = json.dumps({"name": tool_name, "arguments": arguments}, sort_keys=True)
        start = time.perf_counter()
        try:
            filtered_arguments = self.registry.filter_arguments(tool_name, arguments)
        except Exception as exc:
            output = {"error": str(exc), "type": exc.__class__.__name__}
            duration_ms = int((time.perf_counter() - start) * 1000)
            self._record(tool_name, arguments, output, False, duration_ms)
            self.call_count += 1
            return output
        if signature in self.seen_calls:
            output = {"error": "Repeated identical tool call blocked"}
            self._record(tool_name, filtered_arguments, output, False, 0)
            return output
        self.seen_calls.add(signature)
        try:
            output = self.registry.execute(tool_name, filtered_arguments)
            success = True
        except Exception as exc:  # intentionally records tool failures for the agent trace
            output = {"error": str(exc), "type": exc.__class__.__name__}
            success = False
        duration_ms = int((time.perf_counter() - start) * 1000)
        self._record(tool_name, filtered_arguments, output, success, duration_ms)
        self.call_count += 1
        return output

    def _record(self, tool_name: str, arguments: dict, output: dict, success: bool, duration_ms: int) -> None:
        self.db.add(
            AgentToolCall(
                agent_run_id=self.agent_run_id,
                tool_name=tool_name,
                input_json=arguments,
                output_json=output,
                success=success,
                duration_ms=duration_ms,
            )
        )
        self.db.flush()

