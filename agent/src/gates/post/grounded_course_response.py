# можно проверять, что ответ хотя бы упоминает один из реально найденных курсов
from agent.src.gates.base import GateResult


class GroundedCourseResponseGate:
    name = "grounded_course_response"

    def check(self, answer: str, courses: list, **kwargs) -> GateResult:

        if not courses:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="No course data was provided",
            )

        normalized_answer = answer.lower()
        course_names = [course.name for course in courses if course.name]
        contains_course_name = any(name.lower() in normalized_answer for name in course_names)

        if not contains_course_name:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("Generated response does not reference any retrieved course"),
            )

        return GateResult(allowed=True, gate=self.name, data=answer)