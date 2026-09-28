from agent.src.entities.models import LlmEntityCandidates
from agent.src.routing.llm_router import LLMRouter
from agent.src.routing.routes import Route
from agent.src.routing.models import RouteDecision

class Router:
    def __init__(self, llm_router=LLMRouter):
        self.llm_router = llm_router

    def detect(self, message: str, entities: LlmEntityCandidates, context=None) -> RouteDecision:
        llm_decision = self.llm_router.detect(
            message=message,
            entities=entities,
            context=context,
        )

        return RouteDecision(
            route=llm_decision.route,
            source="llm",
            confidence=llm_decision.confidence,
        )
