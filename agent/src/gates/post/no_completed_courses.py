from agent.src.gates.base import GateResult


class NoCompletedCoursesGate:
    name = "no_completed_courses"

    def check(self, selected_course_ids: list[int], completed_course_ids: list[int], **kwargs) -> GateResult:

        completed_ids = set(completed_course_ids)
        invalid_ids = [course_id for course_id in selected_course_ids if course_id in completed_ids]

        if invalid_ids:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("Recommended courses contain completed course ids: " + ", ".join(map(str, invalid_ids))),
            )

        return GateResult(allowed=True, gate=self.name,)