from agent.src.courses.service import build_user_learning_context
from agent.src.recommendation.next_step import find_next_step_candidates
from agent.src.handlers.helper import ground_recommendation_answer, validate_recommended_course_ids
from agent.src.recommendation.service import parse_user_interests
from agent.src.generation.fallback import build_fallback_recommendation

def handle_next_step(request, trace, course_repository, response_generator, llm_client, post_gates, generation_gates):
    # Full learning history
    learning_context = build_user_learning_context(user=request.user, course_repository=course_repository,)

    # Candidate retrieval
    (topics, university_courses, stepik_courses,) = find_next_step_candidates(request=request, course_repository=course_repository,)

    trace.add_evidence(f"Next-step topics: {topics}")

    trace.add_evidence(f"University candidates found: {len(university_courses)}")

    trace.add_evidence(f"Stepik candidates found: {len(stepik_courses)}")

    # No candidates
    if not university_courses and not stepik_courses:
        trace.finish_success(
            user_message=("По твоей текущей истории обучения не удалось найти подходящий следующий курс."),
            reason_code="next_step_not_found",
        )

        return trace.trace

    # LLM generation
    user_interests = parse_user_interests(request.user.interests)

    generation_gate_result = generation_gates.check(
        gate_names=[
            "course_candidates_present",
            "candidate_fields_present",
            "next_step_context_ready",
        ],
        university_courses=university_courses,
        stepik_courses=stepik_courses,
        user_interests=user_interests,
        user_learning_context=learning_context,
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
            user_message=("Недостаточно данных для определения следующего шага обучения."),
        )

        return trace.trace

    result = response_generator.generate(
        message=request.message,
        route=request.route,
        entities=request.entities,
        user_interests=user_interests,
        user_profile={
            "goal": request.user.goal,
            "experience": request.user.experience,
            "academic_results": [item.model_dump() for item in request.user.academic_results],
        },
        user_learning_context=learning_context,
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

    if not selected_course_ids:
        fallback = build_fallback_recommendation(
            university_courses,
            stepik_courses,
            intro="На основе твоих интересов предлагаю следующие варианты:",
        )
        selected_course_ids = fallback.selected_course_ids
        answer = fallback.answer
        trace.add_warning("Deterministic catalog fallback replaced an empty LLM recommendation")
    else:
        answer, selected_course_ids, was_grounded = ground_recommendation_answer(
            answer, selected_course_ids, university_courses, stepik_courses
        )
        if was_grounded:
            trace.add_warning("Added exact selected course titles to a paraphrased LLM response")

    trace.trace.recommended_course_ids = selected_course_ids


    trace.log_llm_call(
        purpose="next_step_response_generation",
        model=llm_client.safe_model_uri,
        input_summary={
            "route": request.route.value,
            "topics": topics,
            "completed_courses_count": len(learning_context.completed),
            "current_courses_count": len(learning_context.current),
            "selected_courses_count": len(learning_context.selected),
            "university_courses_count": len(university_courses),
            "stepik_courses_count": len(stepik_courses),
        },
    )

    # Post-gates
    post_gate_result = post_gates.check(
        request=request,
        answer=answer,
        university_courses=university_courses,
        stepik_courses=stepik_courses,
        user_learning_context=learning_context,
        selected_course_ids=selected_course_ids,
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
            user_message=("Не удалось корректно сформировать следующий шаг обучения."),
        )

        return trace.trace

    trace.add_evidence("Next-step recommendation completed successfully")
    trace.trace.used_course_ids = selected_course_ids
    trace.finish_success(user_message=answer, reason_code="next_step_recommended",)

    return trace.trace
