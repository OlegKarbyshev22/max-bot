from agent.src.entities.models import LlmEntityCandidates
from agent.src.llm.client import LLMClient
from agent.src.routing.routes import Route
from agent.src.models import RecommendationResult
from agent.src.generation.prompts import CONCEPT_EXPLANATION_SYSTEM_PROMPT, SPECIFIC_COURSE_SYSTEM_PROMPT, TOPIC_RECOMMENDATION_SYSTEM_PROMPT, NEXT_STEP_SYSTEM_PROMPT, RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT
from agent.src.generation.fallback import build_fallback_recommendation

class ResponseGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(self, message: str, route: Route, entities, courses=None, user_learning_context=None, university_courses=None, stepik_courses=None, user_interests=None, user_profile=None, conversation_context=None,) -> str | RecommendationResult:

        if route == Route.CONCEPT_EXPLANATION:
            return self._generate_concept_explanation(message=message, entities=entities)

        if route == Route.SPECIFIC_COURSE:
            if not courses:
                raise ValueError("Course data is required for SPECIFIC_COURSE")

            return self._generate_specific_course(
                message=message,
                courses=courses,
                user_learning_context=user_learning_context,
            )

        if route == Route.TOPIC_RECOMMENDATION:
            return self._generate_topic_recommendation(
                message=message,
                entities=entities,
                user_profile=user_profile or {},
                university_courses=university_courses or [],
                stepik_courses=stepik_courses or [],
            )

        if route == Route.NEXT_STEP:
            return self._generate_next_step(
                message=message,
                entities=entities,
                user_interests=user_interests or [],
                user_profile=user_profile or {},
                user_learning_context=user_learning_context,
                university_courses=university_courses or [],
                stepik_courses=stepik_courses or [],
            )

        if route == Route.RECOMMENDATION_EXPLANATION:
            if not courses or conversation_context is None:
                raise ValueError("Recommendation context and courses are required")
            return self._generate_recommendation_explanation(
                message=message,
                courses=courses,
                user_learning_context=user_learning_context,
                conversation_context=conversation_context,
            )

        raise ValueError(f"No response generator implemented for route: {route}")

    def _generate_recommendation_explanation(
        self, message: str, courses: list, user_learning_context, conversation_context
    ) -> str:
        course_data = [self._public_target_course(course) for course in courses]
        learning_data = {
            "completed": [self._public_course_summary(course) for course in user_learning_context.completed],
            "current": [self._public_course_summary(course) for course in user_learning_context.current],
            "selected": [self._public_course_summary(course) for course in user_learning_context.selected],
        }
        user_content = f"""
            Исходный запрос пользователя:
            {conversation_context.recommendation_question}

            Предыдущая рекомендация ассистента:
            {conversation_context.recommendation_answer}

            Новый вопрос пользователя:
            {message}

            Рекомендованные курсы:
            {course_data}

            История обучения пользователя:
            {learning_data}
        """
        messages = [
            {"role": "system", "content": RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        return self.llm_client.complete(messages=messages, temperature=0.2)

    def _public_course_summary(self, course):
        return {
            "name": course.name,
            "source": course.source,
            "description": course.description,
            "level": course.level,
            "complexity_score": course.complexity_score,
        }

    def _public_target_course(self, course) -> dict:
        data = {
            "name": course.name,
            "source": course.source,
            "description": course.description,
            "learning_outcomes": course.learning_outcomes,
            "requirements": course.requirements,
            "program_text": course.program_text,
            "themes": course.themes,
            "concepts": course.concepts,
            "faculty": course.faculty,
            "department": course.department,
            "format": course.format,
        }

        if course.source == "stepik":
            data["level"] = course.level
            data["url"] = course.url

        if course.source == "university":
            data["complexity_score"] = course.complexity_score

        return data

    def _generate_concept_explanation(self, message: str, entities: LlmEntityCandidates) -> str:
        user_content = f"""
            Сообщение пользователя:
            {message}

            Выделенные сущности:
            {entities.model_dump_json()}
            """

        messages = [
            {
                "role": "system",
                "content": CONCEPT_EXPLANATION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        return self.llm_client.complete(messages=messages, temperature=0.3)

    def _generate_specific_course(self, message: str, courses: list, user_learning_context) -> str:

        course_data = [self._public_target_course(course) for course in courses]
        learning_data = {
            "completed": [
                self._public_course_summary(course)
                for course in user_learning_context.completed
            ],
            "current": [
                self._public_course_summary(course)
                for course in user_learning_context.current
            ],
            "selected": [
                self._public_course_summary(course)
                for course in user_learning_context.selected
            ],
        }

        user_content = f"""
            Вопрос пользователя:
            {message}

            Курсы, о которых спрашивает пользователь:
            {course_data}

            Учебный контекст пользователя:
            {learning_data}
            """

        messages = [
            {
                "role": "system",
                "content": SPECIFIC_COURSE_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        return self.llm_client.complete(messages=messages, temperature=0.2)

    def _internal_target_course(self, course) -> dict:
        data = self._public_target_course(course)
        data["id"] = course.id
        return data

    def _generate_topic_recommendation(self, message: str, entities, user_profile: dict, university_courses: list, stepik_courses: list) -> RecommendationResult:

            university_data = [self._internal_target_course(course) for course in university_courses]
            stepik_data = [self._internal_target_course(course) for course in stepik_courses]

            user_content = f"""
                Вопрос пользователя:
                {message}

                Темы и направления:
                {entities.model_dump_json()}

                Данные профиля и успеваемости пользователя:
                {user_profile}

                Университетские кандидаты:
                {university_data}

                Stepik кандидаты:
                {stepik_data}
                """

            messages = [
                {
                    "role": "system",
                    "content": TOPIC_RECOMMENDATION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ]

            try:
                return self.llm_client.complete_json(
                    messages=messages,
                    response_model=RecommendationResult,
                    temperature=0.2,
                )
            except ValueError:
                return build_fallback_recommendation(university_courses, stepik_courses)

    def _generate_next_step(self, message: str, entities, user_interests: list[str], user_profile: dict, user_learning_context, university_courses: list, stepik_courses: list) -> RecommendationResult:

        university_data = [self._internal_target_course(course) for course in university_courses]
        stepik_data = [self._internal_target_course(course) for course in stepik_courses]

        learning_data = {
            "completed": [self._public_course_summary(course) for course in user_learning_context.completed],
            "current": [self._public_course_summary(course) for course in user_learning_context.current],
            "selected": [self._public_course_summary(course) for course in user_learning_context.selected],
        }

        user_content = f"""
            Вопрос пользователя:
            {message}

            Интересы пользователя:
            {user_interests}

            Данные, которые пользователь указал о себе:
            {user_profile}

            Явные темы и направления из текущего запроса:
            {entities.model_dump_json()}

            История обучения:
            {learning_data}

            Университетские кандидаты:
            {university_data}

            Stepik кандидаты:
            {stepik_data}
            """

        messages = [
            {
                "role": "system",
                "content": NEXT_STEP_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        try:
            return self.llm_client.complete_json(
                messages=messages,
                response_model=RecommendationResult,
                temperature=0.2,
            )
        except ValueError:
            return build_fallback_recommendation(
                university_courses,
                stepik_courses,
                intro="На основе твоих интересов предлагаю следующие варианты:",
            )
