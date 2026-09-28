import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from agent.src.generation.fallback import build_fallback_recommendation
from agent.src.models import RecommendationResult
from agent.src.recommendation.service import find_topic_recommendations


class RecommendationCandidateTests(unittest.TestCase):
    def test_excludes_completed_current_and_selected_courses(self) -> None:
        request = SimpleNamespace(
            entities=SimpleNamespace(concepts=["SQL"], directions=["аналитика"]),
            user=SimpleNamespace(
                university_id=1,
                completed_course_ids=[1],
                current_course_ids=[2],
                selected_course_ids=[3],
            ),
        )
        repository = Mock()
        repository.find_university_courses_by_topics.return_value = []
        repository.find_stepik_courses_by_topics.return_value = []
        find_topic_recommendations(request, repository)
        self.assertEqual(
            repository.find_university_courses_by_topics.call_args.kwargs[
                "excluded_course_ids"
            ],
            [1, 2, 3],
        )
        self.assertEqual(
            repository.find_stepik_courses_by_topics.call_args.kwargs[
                "excluded_course_ids"
            ],
            [1, 2, 3],
        )

    def test_recommendation_requires_at_least_one_course(self) -> None:
        with self.assertRaises(ValidationError):
            RecommendationResult(selected_course_ids=[], answer="Нет выбора")

    def test_catalog_fallback_returns_grounded_course_ids_and_text(self) -> None:
        university = SimpleNamespace(
            id=10,
            source="university",
            name="Базы данных",
            complexity_score=3,
            level=None,
            url=None,
        )
        stepik = SimpleNamespace(
            id=20,
            source="stepik",
            name="SQL для начинающих",
            complexity_score=None,
            level="beginner",
            url="https://stepik.org/course/20",
        )
        result = build_fallback_recommendation([university], [stepik])
        self.assertEqual(result.selected_course_ids, [10, 20])
        self.assertIn("Базы данных", result.answer)
        self.assertIn("SQL для начинающих", result.answer)
        self.assertIn("https://stepik.org/course/20", result.answer)


if __name__ == "__main__":
    unittest.main()
