from typing import Any, Literal

from pydantic import BaseModel, Field


class GateLog(BaseModel):
    name: str
    status: Literal["passed", "blocked", "failed"]
    reason: str | None = None


class ToolCallLog(BaseModel):
    name: str
    status: Literal["success", "failed"]
    details: dict[str, Any] = Field(default_factory=dict)


class LlmCallLog(BaseModel):
    purpose: str
    model: str | None = None
    status: Literal["success", "failed"]

    input_summary: dict[str, Any] = Field(default_factory=dict)

    error: str | None = None


class OutcomeLog(BaseModel):
    schema_version: str = Field(default="agent_outcome_v1", serialization_alias="schema")

    kind: Literal["final_answer", "clarification",  "blocked", "error"]

    user_message: str | None = None
    reason_code: str | None = None


class QuestionSpec(BaseModel):
    entities: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    schema_version: str = Field(default="course_agent_trace_v1", serialization_alias="schema")

    number_question: int

    question: str
    route: str | None = None

    question_spec: QuestionSpec = Field(default_factory=QuestionSpec)

    gate_results: list[GateLog] = Field(default_factory=list)

    tool_calls: list[ToolCallLog] = Field(default_factory=list)

    llm_calls: list[LlmCallLog] = Field(default_factory=list)

    evidence: list[str] = Field(default_factory=list)

    llm_used: bool = False

    warnings: list[str] = Field(default_factory=list)

    recommended_course_ids: list[int] = Field(default_factory=list)

    used_course_ids: list[int] = Field(default_factory=list)

    outcome: OutcomeLog | None = None
