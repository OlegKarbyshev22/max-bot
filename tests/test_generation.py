import unittest
from unittest.mock import Mock

from agent.src.courses.models import CourseData, UserCourseSummary, UserLearningContext
from agent.src.entities.models import LlmEntityCandidates
from agent.src.generation.generator import ResponseGenerator
from agent.src.models import RecommendationResult
from agent.src.routing.routes import Route


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock(max_tokens=1200)
        self.generator = ResponseGenerator(self.client)
        self.course = CourseData(id=20, source="stepik", source_course_id="20",
                                 name="SQL для аналитики", description="JOIN и группировка",
                                 level="Начальный", url="https://stepik.org/course/20/")
        self.context = UserLearningContext(
            completed=[UserCourseSummary(id=1, source="stepik", name="Основы Python")],
            current=[UserCourseSummary(id=2, source="stepik", name="Статистика")],
            selected=[UserCourseSummary(id=3, source="stepik", name="Визуализация")],
        )
        self.client.complete_json.return_value = RecommendationResult(
            selected_course_ids=[20], answer="SQL поможет с анализом данных после основ Python.")

    def generate(self, route=Route.TOPIC_RECOMMENDATION):
        return self.generator.generate(
            message="Подбери SQL", route=route, entities=LlmEntityCandidates(),
            user_profile={"goal": "Стать аналитиком", "experience": "Основы Python"},
            user_learning_context=self.context, stepik_courses=[self.course],
        )

    def test_topic_passes_profile_history_and_course_content(self):
        self.generate()
        kwargs = self.client.complete_json.call_args.kwargs
        prompt = kwargs["messages"][1]["content"]
        for value in ("Стать аналитиком", "Основы Python", "completed", "current",
                      "selected", "Статистика", "Визуализация", "JOIN и группировка"):
            self.assertIn(value, prompt)
        self.assertEqual(kwargs["max_tokens"], 5000)

    def test_invalid_json_recovers_personalized_text_for_both_routes(self):
        for route in (Route.TOPIC_RECOMMENDATION, Route.NEXT_STEP):
            with self.subTest(route=route):
                self.client.complete_json.side_effect = ValueError("invalid JSON")
                self.client.complete.return_value = "SQL: JOIN дополнит ваши основы Python для аналитики."
                result = self.generate(route)
                self.assertEqual(result.selected_course_ids, [20])
                self.assertEqual(result.answer, self.client.complete.return_value)
                messages = self.client.complete.call_args.kwargs["messages"]
                self.assertIn("Стать аналитиком", messages[1]["content"])
                self.assertIn("Основы Python", messages[1]["content"])
                self.assertIn(self.course.name, messages[2]["content"])

    def test_invalid_catalog_id_triggers_recovery(self):
        self.client.complete_json.return_value = RecommendationResult(selected_course_ids=[999], answer="Курс")
        self.client.complete.return_value = "SQL для аналитики"
        self.assertEqual(self.generate().selected_course_ids, [20])
        self.client.complete.assert_called_once()

    def test_total_generation_failure_is_explicit(self):
        self.client.complete_json.side_effect = ValueError("invalid JSON")
        self.client.complete.side_effect = ValueError("empty response")
        result = self.generate()
        self.assertIn("Не удалось сформировать персональное объяснение", result.answer)
        self.assertNotIn("соответствует теме запроса", result.answer)


if __name__ == "__main__":
    unittest.main()
