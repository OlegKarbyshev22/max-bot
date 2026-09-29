import json
import re
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError


ModelT = TypeVar("ModelT", bound=BaseModel)


def extract_json(text: str) -> str:
    value = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1).strip()
    start = min((pos for pos in (value.find("{"), value.find("[")) if pos >= 0), default=-1)
    if start > 0:
        value = value[start:]
    return value


class LLMClient:
    def __init__(
        self,
        client: OpenAI,
        model: str,
        max_tokens: int = 1200,
        local_mode: bool = False,
        use_json_schema: bool = True,
    ):
        self.client = client
        self.model = model.strip()
        self.max_tokens = max_tokens
        self.local_mode = local_mode
        self.use_json_schema = use_json_schema

    @property
    def model_uri(self) -> str:
        return self.model

    @property
    def safe_model_uri(self) -> str:
        return self.model

    def _messages(self, messages: list[dict]) -> list[dict]:
        result = [dict(message) for message in messages]
        if self.local_mode and result and result[0].get("role") == "system":
            result[0]["content"] = f"{result[0].get('content', '')}\n/no_think"
        return result

    def _provider_options(self) -> dict:
        if not self.local_mode:
            return {}
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}

    def complete(self, messages: list[dict], temperature: float = 0, max_tokens: int | None = None) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self._messages(messages),
            temperature=temperature,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            **self._provider_options(),
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty response")
        return content.strip()

    def complete_json(
        self,
        messages: list[dict],
        response_model: type[ModelT],
        temperature: float = 0,
        max_tokens: int | None = None,
    ) -> ModelT:
        schema = response_model.model_json_schema()
        request_messages = self._messages(messages)
        last_error: Exception | None = None

        for attempt in range(2):
            request_options = {
                "model": self.model,
                "messages": request_messages,
                "temperature": temperature,
                "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
                **self._provider_options(),
            }
            if self.use_json_schema:
                request_options["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_model.__name__,
                        "strict": True,
                        "schema": schema,
                    },
                }
            response = self.client.chat.completions.create(
                **request_options,
            )
            content = response.choices[0].message.content or ""
            try:
                return response_model.model_validate_json(extract_json(content))
            except (ValidationError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                request_messages = request_messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "Исправь ответ. Верни только валидный JSON по заданной схеме, без Markdown.",
                    },
                ]

        raise ValueError(f"LLM returned invalid structured response: {last_error}")
