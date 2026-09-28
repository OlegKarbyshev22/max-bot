def validate_recommended_course_ids(selected_course_ids: list[int], university_courses: list, stepik_courses: list) -> tuple[list[int], list[int]]:
    allowed_ids = {course.id for course in university_courses + stepik_courses}

    valid_ids = [course_id for course_id in selected_course_ids if course_id in allowed_ids]

    invalid_ids = [course_id for course_id in selected_course_ids if course_id not in allowed_ids]

    return valid_ids, invalid_ids


def ground_recommendation_answer(
    answer: str,
    selected_course_ids: list[int],
    university_courses: list,
    stepik_courses: list,
) -> tuple[str, list[int], bool]:
    """Keep a personalized LLM answer while making its selected courses explicit.

    Cloud providers can return a valid structured list of IDs but paraphrase course
    titles in the prose. The post-gates require exact titles, so add a short factual
    list instead of replacing the whole response with a generic fallback.
    """
    courses_by_id = {
        course.id: course for course in university_courses + stepik_courses
    }
    selected = list(
        dict.fromkeys(
            course_id for course_id in selected_course_ids if course_id in courses_by_id
        )
    )

    # The product rule is to show at least one university course first when one is
    # available. Preserve the model's order for all remaining choices.
    if university_courses and not any(
        courses_by_id[course_id].source == "university" for course_id in selected
    ):
        selected = [university_courses[0].id] + selected[:4]

    # University courses must be visible before external courses in the response.
    selected_courses = sorted(
        (courses_by_id[course_id] for course_id in selected),
        key=lambda course: 0 if course.source == "university" else 1,
    )
    selected = [course.id for course in selected_courses]
    normalized_answer = answer.lower()
    missing_titles = [
        course for course in selected_courses
        if course.name and course.name.lower() not in normalized_answer
    ]
    missing_urls = [
        course for course in selected_courses
        if course.source == "stepik"
        and getattr(course, "url", None)
        and course.url not in answer
    ]
    if not selected_courses or (not missing_titles and not missing_urls):
        return answer, selected, False

    course_lines = ["Подобранные курсы:"]
    for course in selected_courses:
        course_lines.append(f"— {course.name}")
        if course.source == "stepik" and getattr(course, "url", None):
            course_lines.append(f"  Ссылка: {course.url}")
    return "\n".join(course_lines) + f"\n\n{answer.lstrip()}", selected, True
