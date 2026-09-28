from agent.src.courses.service import build_user_learning_context


def handle_recommendation_followup(
    request,
    trace,
    course_repository,
    response_generator,
    llm_client,
    post_gates,
):
    course_ids = request.context.recommended_course_ids
    courses = course_repository.get_by_registry_ids(course_ids)
    if not courses:
        trace.finish_blocked(
            reason_code="recommendation_context_missing",
            user_message="Я не вижу предыдущую рекомендацию. Попроси подобрать курсы ещё раз.",
        )
        return trace.trace

    learning_context = build_user_learning_context(
        user=request.user,
        course_repository=course_repository,
    )
    answer = response_generator.generate(
        message=request.message,
        route=request.route,
        entities=request.entities,
        courses=courses,
        user_learning_context=learning_context,
        conversation_context=request.context,
    )
    trace.log_llm_call(
        purpose="recommendation_followup_response_generation",
        model=llm_client.safe_model_uri,
        input_summary={
            "route": request.route.value,
            "course_ids": [course.id for course in courses],
        },
    )
    post_gate_result = post_gates.check(request=request, answer=answer)
    for result in post_gate_result.results:
        trace.log_gate(
            name=result.gate or "unknown",
            allowed=result.allowed,
            reason=result.reason,
        )
    if not post_gate_result.allowed:
        failed_gate = post_gate_result.results[-1]
        trace.finish_blocked(
            reason_code=failed_gate.gate or "post_gate_failed",
            user_message="Не удалось корректно ответить на уточнение.",
        )
        return trace.trace

    trace.trace.used_course_ids = [course.id for course in courses]
    trace.finish_success(
        user_message=answer,
        reason_code="recommendation_followup_answered",
    )
    return trace.trace
