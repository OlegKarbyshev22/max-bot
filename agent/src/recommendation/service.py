from agent.src.courses.repository import CourseRepository
from agent.src.courses.service import get_user_course_ids

def extract_recommendation_topics(entities) -> list[str]:
    topics = []
    topics.extend(entities.concepts or [])
    topics.extend(entities.directions or [])

    # убрать дубли без потери порядка
    return list(dict.fromkeys(topics))


def find_topic_recommendations(request, course_repository: CourseRepository):
    topics = list(dict.fromkeys((request.entities.concepts or []) + (request.entities.directions or [])))
    excluded_course_ids = get_user_course_ids(request.user)

    university_courses = (
        course_repository.find_university_courses_by_topics(
            topics=topics,
            university_id=request.user.university_id,
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

    return university_courses, stepik_courses

def parse_user_interests(interests: str) -> list[str]:
    items = [item.strip() for item in interests.split(",") if item.strip()]

    return list(dict.fromkeys(items))
