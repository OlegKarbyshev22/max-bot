import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import BaseModel

from agent.src.llm.client import LLMClient, extract_json


class Reply(BaseModel):
    value: int


def response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class LLMClientTests(unittest.TestCase):
    def test_extracts_markdown_fence(self) -> None:
        self.assertEqual(extract_json('```json\n{"value": 7}\n```'), '{"value": 7}')

    def test_structured_response_retries_invalid_json(self) -> None:
        openai_client = Mock()
        openai_client.chat.completions.create.side_effect = [
            response("not-json"),
            response('```json\n{"value": 9}\n```'),
        ]
        client = LLMClient(openai_client, "local-model", local_mode=True)
        parsed = client.complete_json([{"role": "system", "content": "test"}], Reply)
        self.assertEqual(parsed.value, 9)
        self.assertEqual(openai_client.chat.completions.create.call_count, 2)
        kwargs = openai_client.chat.completions.create.call_args.kwargs
        self.assertFalse(kwargs["extra_body"]["chat_template_kwargs"]["enable_thinking"])

    def test_cloud_request_has_no_llama_specific_options(self) -> None:
        openai_client = Mock()
        openai_client.chat.completions.create.return_value = response("ok")
        client = LLMClient(openai_client, "cloud-model")
        self.assertEqual(client.complete([{"role": "system", "content": "test"}]), "ok")
        kwargs = openai_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("extra_body", kwargs)
        self.assertEqual(kwargs["messages"][0]["content"], "test")

    def test_generation_budget_override_does_not_change_routing_budget(self) -> None:
        sdk = Mock()
        sdk.chat.completions.create.return_value = response('{"value": 7}')
        client = LLMClient(sdk, "model", max_tokens=1200)
        client.complete_json([], Reply, max_tokens=5000)
        self.assertEqual(sdk.chat.completions.create.call_args.kwargs["max_tokens"], 5000)
        client.complete([], max_tokens=5000)
        self.assertEqual(sdk.chat.completions.create.call_args.kwargs["max_tokens"], 5000)
        client.complete([])
        self.assertEqual(sdk.chat.completions.create.call_args.kwargs["max_tokens"], 1200)

    def test_structured_response_can_use_prompt_only_json(self) -> None:
        openai_client = Mock()
        openai_client.chat.completions.create.return_value = response('{"value": 7}')
        client = LLMClient(openai_client, "proxy-model", use_json_schema=False)
        self.assertEqual(
            client.complete_json([{"role": "system", "content": "JSON"}], Reply).value,
            7,
        )
        kwargs = openai_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("response_format", kwargs)


if __name__ == "__main__":
    unittest.main()
