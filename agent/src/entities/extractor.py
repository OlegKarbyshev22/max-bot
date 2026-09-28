from agent.src.entities.models import LlmEntityCandidates
from agent.src.entities.prompts import ENTITY_EXTRACTION_SYSTEM_PROMPT
from agent.src.llm.client import LLMClient


class EntityExtractor:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract(self, message: str) -> LlmEntityCandidates:
        messages = [
            {
                "role": "system",
                "content": ENTITY_EXTRACTION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": message,
            },
        ]

        return self.llm_client.complete_json(
            messages=messages,
            response_model=LlmEntityCandidates,
            temperature=0,
        )
