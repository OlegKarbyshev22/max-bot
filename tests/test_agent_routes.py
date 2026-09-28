import unittest
from unittest.mock import Mock

from agent.src.entities.models import LlmEntityCandidates
from agent.src.routing.llm_router import LLMRouter
from agent.src.routing.models import LlmRouteDecision
from agent.src.routing.routes import Route


class AgentRouteTests(unittest.TestCase):
    def test_all_supported_routes_from_structured_llm(self) -> None:
        for route in Route:
            with self.subTest(route=route.value):
                llm = Mock()
                llm.complete_json.return_value = LlmRouteDecision(route=route, confidence=0.9)
                result = LLMRouter(llm).detect(
                    "тестовый вопрос", LlmEntityCandidates()
                )
                self.assertEqual(result.route, route)
                llm.complete_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
