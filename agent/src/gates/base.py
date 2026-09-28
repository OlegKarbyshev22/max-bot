from typing import Any

from pydantic import BaseModel, Field


class GateResult(BaseModel):
    allowed: bool
    gate: str | None = None
    reason: str | None = None
    data: Any = None


class GatePipelineResult(BaseModel):
    allowed: bool
    results: list[GateResult] = Field(default_factory=list)


class PreGate:
    name: str

    def check(self, request) -> GateResult:
        raise NotImplementedError