from agent.src.courses.models import UserLearningContext
from agent.src.courses.repository import CourseRepository
from agent.models import UserContext


def build_user_learning_context(
    user: UserContext,
    course_repository: CourseRepository,
) -> UserLearningContext:
    completed = course_repository.get_courses_by_registry_ids(
        user.completed_course_ids
    )

    current = course_repository.get_courses_by_registry_ids(
        user.current_course_ids
    )

    selected = course_repository.get_courses_by_registry_ids(
        user.selected_course_ids
    )

    return UserLearningContext(
        completed=completed,
        current=current,
        selected=selected,
    )

def get_user_course_ids(user: UserContext) -> list[int]:
    return list(
        dict.fromkeys(
            user.completed_course_ids
            + user.current_course_ids
            + user.selected_course_ids
        )
    )