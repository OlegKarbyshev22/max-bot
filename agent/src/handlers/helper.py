def validate_recommended_course_ids(selected_course_ids: list[int], university_courses: list, stepik_courses: list) -> tuple[list[int], list[int]]:
    allowed_ids = {course.id for course in university_courses + stepik_courses}

    valid_ids = [course_id for course_id in selected_course_ids if course_id in allowed_ids]

    invalid_ids = [course_id for course_id in selected_course_ids if course_id not in allowed_ids]

    return valid_ids, invalid_ids