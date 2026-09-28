from agent.src.gates.base import GateResult

class GroundedRecommendationGate:
    name = "grounded_recommendation"

    def check(self, answer: str, university_courses: list, stepik_courses: list, **kwargs) -> GateResult:

        candidates = university_courses + stepik_courses

        if not candidates:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="No candidate courses were provided",
            )

        normalized_answer = answer.lower()

        mentioned = [course.name for course in candidates if course.name and course.name.lower() in normalized_answer]

        if not mentioned:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("Response does not mention any retrieved course"),
            )

        return GateResult(allowed=True, gate=self.name, data=answer)