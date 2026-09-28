from agent.src.gates.base import GateResult


class CourseAccessGate:
    name = "course_access"

    def check(self, user, course,) -> GateResult:

        # Общий курс
        if course.source == "stepik":
            return GateResult(allowed=True, gate=self.name)

        # Защита на случай плохих данных
        if course.source != "university":
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=(f"Unsupported course source: {course.source}"),
            )

        # University course но у пользователя нет университета
        if user.university_id is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="User has no university",
            )

        # У курса должен быть university_id
        if course.university_id is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("University course has no university_id"),
            )

        # Сравниваем
        if user.university_id != course.university_id:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("User university does not match course university"),
            )

        return GateResult(allowed=True, gate=self.name)