# проверяем, что если университетские курсы есть, они действительно появились раньше Stepik

from agent.src.gates.base import GateResult

class UniversityPriorityGate:
    name = "university_priority"

    def check(self, answer: str, university_courses: list, stepik_courses: list, **kwargs) -> GateResult:

        if not university_courses:
            return GateResult(
                allowed=True,
                gate=self.name,
                data=answer,
            )

        normalized_answer = answer.lower()

        university_positions = [normalized_answer.find(course.name.lower()) for course in university_courses if course.name and course.name.lower() in normalized_answer]
        stepik_positions = [normalized_answer.find(course.name.lower()) for course in stepik_courses if course.name and course.name.lower() in normalized_answer]

        if not university_positions:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="University courses were not included in response",
            )

        if stepik_positions:
            first_university = min(university_positions)
            first_stepik = min(stepik_positions)

            if first_stepik < first_university:
                return GateResult(
                    allowed=False,
                    gate=self.name,
                    reason=("Stepik courses appear before university courses"),
                )

        return GateResult(allowed=True, gate=self.name, data=answer)