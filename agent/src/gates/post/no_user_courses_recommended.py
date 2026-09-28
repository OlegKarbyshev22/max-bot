from agent.src.gates.base import GateResult

class NoUserCoursesRecommendedGate:
    name = "no_user_courses_recommended"

    def check(self, selected_course_ids: list[int], request, **kwargs,) -> GateResult:
        user_course_ids = set(request.user.completed_course_ids + request.user.current_course_ids + request.user.selected_course_ids)
        invalid_ids = [course_id for course_id in selected_course_ids if course_id in user_course_ids]

        if invalid_ids:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("Recommended courses contain courses already associated with the user: " + ", ".join(map(str, invalid_ids))),
            )

        return GateResult(allowed=True, gate=self.name,)