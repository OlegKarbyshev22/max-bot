import json
import tempfile
import unittest

from agent.src.logging.logger import AgentLogger
from agent.src.logging.models import AgentTrace, OutcomeLog, QuestionSpec


class SafeLoggingTests(unittest.TestCase):
    def test_free_form_user_and_answer_text_are_redacted(self) -> None:
        trace = AgentTrace(
            number_question=1,
            question="секретный вопрос пользователя",
            question_spec=QuestionSpec(entities={"free_text": "персональные данные"}),
            outcome=OutcomeLog(
                kind="final_answer",
                user_message="персонализированный ответ",
                reason_code="ok",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = AgentLogger(directory).save_batch([trace])
            payload = json.loads(path.read_text(encoding="utf-8"))
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("секретный вопрос", serialized)
        self.assertNotIn("персональные данные", serialized)
        self.assertNotIn("персонализированный ответ", serialized)
        self.assertEqual(payload["results"][0]["schema"], "course_agent_trace_v1")


if __name__ == "__main__":
    unittest.main()
