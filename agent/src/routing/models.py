from pydantic import BaseModel, Field
from agent.src.routing.routes import Route
from typing import Literal

class LlmRouteDecision(BaseModel):
    route: Route
    confidence: float = Field(ge=0, le=1)

class RouteDecision(BaseModel):
    route: Route
    source: Literal["regex", "llm"]
    confidence: float | None = None