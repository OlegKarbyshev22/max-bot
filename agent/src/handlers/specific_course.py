from agent.src.courses.service import build_user_learning_context
from agent.src.recommendation.service import find_topic_recommendations

def handle_specific_course(request, trace, course_repository, course_access_gate, response_generator, llm_client, post_gates, generation_gates):
    course_name = request.entities.course_names[0]
    courses = course_repository.find_exact_by_name(course_name)

    trace.add_evidence(f"Exact course lookup performed for: {course_name}")

    if not courses:
        trace.finish_success(
            user_message=f'Курс с названием "{course_name}" не найден.',
            reason_code="course_not_found",
        )
        return trace.trace

    accessible_courses = []

    for course in courses:
        access_result = course_access_gate.check(user=request.user, course=course)

        trace.log_gate(
            name=f"course_access:{course.id}",
            allowed=access_result.allowed,
            reason=access_result.reason,
        )

        if access_result.allowed:
            accessible_courses.append(course)

    if not accessible_courses:
        trace.finish_blocked(
            reason_code="course_access_denied",
            user_message="Найденные курсы недоступны для твоего университета.",
        )
        return trace.trace

    learning_context = build_user_learning_context(
        user=request.user,
        course_repository=course_repository,
    )

    generation_gate_result = generation_gates.check(
        gate_names=[
            "course_candidates_present",
            "candidate_fields_present",
        ],
        courses=accessible_courses,
    )

    for result in generation_gate_result.results:
        trace.log_gate(
            name=result.gate or "unknown",
            allowed=result.allowed,
            reason=result.reason,
        )

    if not generation_gate_result.allowed:
        failed_gate = generation_gate_result.results[-1]

        trace.finish_blocked(
            reason_code=(failed_gate.gate or "generation_input_failed"),
            user_message=("Недостаточно данных для формирования ответа по курсу."),
        )

        return trace.trace

    answer = response_generator.generate(
        message=request.message,
        route=request.route,
        entities=request.entities,
        courses=accessible_courses,
        user_learning_context=learning_context,
    )

    trace.log_llm_call(
        purpose="specific_course_response_generation",
        model=llm_client.safe_model_uri,
        input_summary={
            "route": request.route.value,
            "course_ids": [course.id for course in accessible_courses],
        },
    )

    post_gate_result = post_gates.check(
        request=request,
        answer=answer,
        courses=accessible_courses,
        user_learning_context=learning_context,
    )

    for result in post_gate_result.results:
        trace.log_gate(
            name=result.gate or "unknown",
            allowed=result.allowed,
            reason=result.reason,
        )

    if not post_gate_result.allowed:
        failed_gate = post_gate_result.results[-1]

        trace.finish_blocked(
            reason_code=(failed_gate.gate or "post_gate_failed"),
            user_message=("Не удалось корректно сформировать ответ по курсу."),
        )

        return trace.trace

    trace.trace.used_course_ids = [course.id for course in accessible_courses]

    trace.finish_success(
        user_message=answer,
        reason_code="course_answer_generated",
    )

    return trace.trace