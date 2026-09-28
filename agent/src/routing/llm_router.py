from agent.src.entities.models import LlmEntityCandidates
from agent.src.llm.client import LLMClient
from agent.src.routing.models import LlmRouteDecision
from agent.src.routing.prompts import ROUTE_DETECTION_SYSTEM_PROMPT


class LLMRouter:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def detect(self, message: str, entities: LlmEntityCandidates, context=None) -> LlmRouteDecision:

        user_content = f"""
        Сообщение пользователя:
        {message}

        Выделенные сущности:
        {entities.model_dump_json()}

        Контекст предыдущей рекомендации:
        {context.model_dump_json() if context else '{}'}
        """

        messages = [
            {
                "role": "system",
                "content": ROUTE_DETECTION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        return self.llm_client.complete_json(
            messages=messages,
            response_model=LlmRouteDecision,
            temperature=0,
        )
