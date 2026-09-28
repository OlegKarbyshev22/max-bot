from agent.src.recommendation.service import find_topic_recommendations
from agent.src.courses.service import build_user_learning_context
from agent.src.handlers.helper import validate_recommended_course_ids
from agent.src.generation.fallback import build_fallback_recommendation


def handle_topic_recommendation(request, trace, course_repository, response_generator, llm_client, post_gates, generation_gates):
    university_courses, stepik_courses = find_topic_recommendations(request=request, course_repository=course_repository,)

    trace.add_evidence(f"University candidates found: {len(university_courses)}")

    trace.add_evidence(f"Stepik candidates found: {len(stepik_courses)}")

    if not university_courses and not stepik_courses:
        trace.finish_success(
            user_message="По этим темам подходящих курсов не нашлось.",
            reason_code="topic_courses_not_found",
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
        university_courses=university_courses,
        stepik_courses=stepik_courses,
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
            user_message=("Недостаточно данных для формирования рекомендаций."),
        )

        return trace.trace


    result = response_generator.generate(
        message=request.message,
        route=request.route,
        entities=request.entities,
        user_profile={
            "goal": request.user.goal,
            "experience": request.user.experience,
            "academic_results": [item.model_dump() for item in request.user.academic_results],
        },
        university_courses=university_courses,
        stepik_courses=stepik_courses,
    )

    answer = result.answer

    selected_course_ids, invalid_ids = validate_recommended_course_ids(
        selected_course_ids=result.selected_course_ids,
        university_courses=university_courses,
        stepik_courses=stepik_courses,
    )

    if invalid_ids:
        trace.add_warning(f"LLM returned invalid course ids: {invalid_ids}")

    trace.trace.recommended_course_ids = selected_course_ids

    trace.log_llm_call(
        purpose="topic_recommendation_response_generation",
        model=llm_client.safe_model_uri,
        input_summary={
            "route": request.route.value,
            "university_courses_count": len(university_courses),
            "stepik_courses_count": len(stepik_courses),
            "recommended_course_ids": selected_course_ids,
        },
    )

    if invalid_ids:
        trace.add_warning(f"LLM returned invalid course ids: {invalid_ids}")

    selected_courses = [
        course for course in university_courses + stepik_courses
        if course.id in selected_course_ids
    ]
    if not selected_course_ids or not any(
        course.name and course.name.lower() in answer.lower() for course in selected_courses
    ):
        fallback = build_fallback_recommendation(university_courses, stepik_courses)
        selected_course_ids = fallback.selected_course_ids
        answer = fallback.answer
        trace.add_warning("Deterministic catalog fallback replaced an empty or ungrounded LLM recommendation")

    trace.trace.recommended_course_ids = selected_course_ids

    trace.log_llm_call(
        purpose="topic_recommendation_response_generation",
        model=llm_client.safe_model_uri,
        input_summary={
            "route": request.route.value,
            "university_courses_count": len(university_courses),
            "stepik_courses_count": len(stepik_courses),
        },
    )

    post_gate_result = post_gates.check(
        request=request,
        answer=answer,
        university_courses=university_courses,
        stepik_courses=stepik_courses,
        selected_course_ids=selected_course_ids,
        completed_course_ids=request.user.completed_course_ids,
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
            reason_code=failed_gate.gate or "post_gate_failed",
            user_message="Не удалось корректно сформировать рекомендации.",
        )

        return trace.trace

    trace.add_evidence("Topic recommendation handler completed successfully")

    trace.trace.used_course_ids = selected_course_ids

    trace.finish_success(user_message=answer, reason_code="topic_courses_recommended",)

    return trace.trace
