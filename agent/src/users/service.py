from agent.models import UserContext
from agent.src.users.repository import UserRepository


def build_user_context(user_id: str, user_repository: UserRepository) -> UserContext:

    user_row = user_repository.get_by_max_user_id(user_id)

    if user_row is None:
        raise ValueError(f"User '{user_id}' not found")

    course_ids = user_repository.get_user_course_ids(db_user_id=user_row["id"])
    academic_results = user_repository.get_academic_results(db_user_id=user_row["id"])

    return UserContext(
        user_id=user_row["max_user_id"],
        role=user_row["role"],
        university_id=user_row["university_id"],
        interests=user_row["interests"],
        goal=user_row.get("goal") or "",
        experience=user_row.get("experience") or "",
        completed_course_ids=course_ids["completed"],
        current_course_ids=course_ids["in_progress"],
        selected_course_ids=course_ids["selected"],
        academic_results=academic_results,
        preferences={},
    )
