from agent.src.models import RecommendationResult


def build_fallback_recommendation(
    university_courses: list,
    stepik_courses: list,
    intro: str = "Подобрал подходящие варианты из каталога:",
) -> RecommendationResult:
    selected = (university_courses + stepik_courses)[:3]
    if not selected:
        raise ValueError("Fallback recommendation requires at least one course")

    lines = ["🎯 ПОДБОРКА КУРСОВ", intro]
    for course in selected:
        details = []
        if course.source == "university" and course.complexity_score is not None:
            details.append(f"сложность: {course.complexity_score}")
        if course.source == "stepik" and course.level:
            details.append(f"уровень: {course.level}")
        lines.append(f"\n📌 {course.name}")
        if details:
            lines.append("Характеристики: " + ", ".join(details))
        lines.append("Почему подходит: соответствует теме запроса.")
        if course.source == "stepik" and course.url:
            lines.append(f"Открыть курс: {course.url}")

    return RecommendationResult(
        selected_course_ids=[course.id for course in selected],
        answer="\n".join(lines),
    )
