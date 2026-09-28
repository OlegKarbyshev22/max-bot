from agent.src.logging.models import AgentTrace, GateLog, LlmCallLog, OutcomeLog
from agent.src.logging.models import ToolCallLog

class TraceContext:
    def __init__(self, number_question: int, question: str, logger):
        self.trace = AgentTrace(number_question=number_question, question=question)
        self.logger = logger
        self.trace = AgentTrace(number_question=number_question, question=question)

    def save(self) -> None:
        self.logger.save(self.trace)

    def log_entities(self, entities) -> None:
        entities_dict = entities.model_dump()
        self.trace.question_spec.entities = entities_dict
        self.trace.evidence.append("Entities extracted")

    def log_route(self, route, source: str, confidence: float | None = None) -> None:
        route_name = (
            route.value
            if hasattr(route, "value")
            else str(route)
        )

        self.trace.route = route_name
        self.trace.evidence.append(f"Route selected: {route_name}")
        self.trace.evidence.append(f"Route source: {source}")

        if confidence is not None:
            self.trace.evidence.append(f"Route confidence: {confidence}")

    def log_gate(self, name: str, allowed: bool, reason: str | None = None) -> None:
        self.trace.gate_results.append(
            GateLog(
                name=name,
                status="passed" if allowed else "blocked",
                reason=reason,
            )
        )

    def log_llm_call(self, purpose: str, model: str | None, input_summary: dict | None = None,
                    status: str = "success", error: str | None = None) -> None:
        self.trace.llm_used = True
        self.trace.llm_calls.append(
            LlmCallLog(
                purpose=purpose,
                model=model,
                status=status,
                input_summary=input_summary or {},
                error=error,
            )
        )

    def log_tool_call(self, name: str, status: str, details: dict | None = None) -> None:

        self.trace.tool_calls.append(
            ToolCallLog(
                name=name,
                status=status,
                details=details or {},
            )
        )

    def add_evidence(self, message: str) -> None:
        self.trace.evidence.append(message)

    def add_warning(self, warning: str) -> None:
        self.trace.warnings.append(warning)

    def finish_success(self, user_message: str, reason_code: str) -> None:
        self.trace.outcome = OutcomeLog(
            kind="final_answer",
            user_message=user_message,
            reason_code=reason_code,
        )

    def finish_blocked(self, reason_code: str, user_message: str | None = None) -> None:
        self.trace.outcome = OutcomeLog(
            kind="blocked",
            user_message=user_message,
            reason_code=reason_code,
        )

    def finish_error(self, reason_code: str, user_message: str | None = None) -> None:
        self.trace.outcome = OutcomeLog(
            kind="error",
            user_message=user_message,
            reason_code=reason_code,
        )

    def finish_clarification(self, user_message: str, reason_code: str) -> None:
        self.trace.outcome = OutcomeLog(
            kind="clarification",
            user_message=user_message,
            reason_code=reason_code,
        )