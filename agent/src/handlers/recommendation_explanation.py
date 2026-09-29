from agent.src.courses.service import build_user_learning_context


def handle_recommendation_explanation(
    request, trace, course_repository, response_generator, post_gates, generation_gates
):
    """Explain only the courses saved with the immediately preceding recommendation."""
    courses = course_repository.get_by_registry_ids(request.context.recommended_course_ids)
    if not courses:
        trace.finish_blocked(
            reason_code="recommendation_context_missing",
            user_message="Я не вижу предыдущую рекомендацию. Попроси подобрать курсы ещё раз.",
        )
        return trace.trace

    generation_result = generation_gates.check(
        gate_names=["course_candidates_present", "candidate_fields_present"],
        university_courses=[course for course in courses if course.source == "university"],
        stepik_courses=[course for course in courses if course.source == "stepik"],
    )
    for result in generation_result.results:
        trace.log_gate(name=result.gate or "unknown", allowed=result.allowed, reason=result.reason)
    if not generation_result.allowed:
        trace.finish_blocked(
            reason_code=generation_result.results[-1].gate or "generation_input_failed",
            user_message="Не удалось получить данные о курсах из предыдущей рекомендации.",
        )
        return trace.trace

    learning_context = build_user_learning_context(request.user, course_repository)
    answer = response_generator.generate(
        message=request.message,
        route=request.route,
        entities=request.entities,
        courses=courses,
        user_profile={
            "goal": request.user.goal,
            "experience": request.user.experience,
            "interests": request.user.interests,
            "academic_results": [item.model_dump() for item in request.user.academic_results],
        },
        user_learning_context=learning_context,
        conversation_context=request.context,
    )
    trace.log_llm_call(
        purpose="recommendation_explanation_response_generation",
        model=response_generator.llm_client.safe_model_uri,
        input_summary={"route": request.route.value, "course_ids": [course.id for course in courses]},
    )
    post_gate_result = post_gates.check(request=request, answer=answer, courses=courses)
    for result in post_gate_result.results:
        trace.log_gate(name=result.gate or "unknown", allowed=result.allowed, reason=result.reason)
    if not post_gate_result.allowed:
        trace.finish_blocked(
            reason_code=post_gate_result.results[-1].gate or "post_gate_failed",
            user_message="Не удалось сформировать корректное объяснение предыдущей рекомендации.",
        )
        return trace.trace

    trace.trace.used_course_ids = [course.id for course in courses]
    trace.finish_success(user_message=answer, reason_code="recommendation_explanation_generated")
    return trace.trace
