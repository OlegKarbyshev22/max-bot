from agent.src.gates.base import GateResult

# Проверяет, что после retrieval/access filtering у нас вообще есть хотя бы один курс для передачи в LLM.
class CourseCandidatesPresentGate:
    name = "course_candidates_present"

    def check(self, university_courses=None, stepik_courses=None, courses=None, **kwargs) -> GateResult:

        all_courses = []

        if courses:
            all_courses.extend(courses)

        if university_courses:
            all_courses.extend(university_courses)

        if stepik_courses:
            all_courses.extend(stepik_courses)

        if not all_courses:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="No course candidates available for generation",
            )

        return GateResult(
            allowed=True,
            gate=self.name,
        )