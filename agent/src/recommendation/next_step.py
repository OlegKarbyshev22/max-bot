from agent.src.courses.service import get_user_course_ids
from agent.src.recommendation.service import parse_user_interests


def find_next_step_candidates(request, course_repository):
    user = request.user

    excluded_course_ids = get_user_course_ids(user)

    # Interests пользователя - основной источник
    user_interests = parse_user_interests(user.interests)

    # Темы из истории - дополнительный источник
    history_topics = (course_repository.get_topics_by_course_ids(excluded_course_ids) if excluded_course_ids else [])

    # Явные темы текущего запроса
    explicit_topics = ((request.entities.concepts or []) + (request.entities.directions or []))

    topics = list(dict.fromkeys(user_interests + explicit_topics + history_topics))

    university_courses = (
        course_repository.find_university_courses_by_topics(
            topics=topics,
            university_id=user.university_id,
            excluded_course_ids=excluded_course_ids,
            limit=20,
        )
    )

    stepik_courses = (
        course_repository.find_stepik_courses_by_topics(
            topics=topics,
            excluded_course_ids=excluded_course_ids,
            limit=20,
        )
    )

    return (topics, university_courses, stepik_courses, )