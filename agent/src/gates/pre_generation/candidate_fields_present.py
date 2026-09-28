from agent.src.gates.base import GateResult
# Проверяет минимально необходимые поля у каждого курса-кандидата id, name и source должны быть заполнены.

class CandidateFieldsPresentGate:
    name = "candidate_fields_present"

    def check(self, university_courses=None, stepik_courses=None, courses=None, **kwargs) -> GateResult:

        all_courses = ((courses or []) + (university_courses or []) + (stepik_courses or []))

        invalid = []

        for course in all_courses:
            if not course.id or not course.name or not course.source:
                invalid.append(course.id)

        if invalid:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Course candidates have missing required fields: {invalid}",
            )

        return GateResult(allowed=True, gate=self.name,)