from agent.models import AgentRequest, UserContext
from agent.src.models import ConversationContext
from agent.src.logging.context import TraceContext
from agent.src.routing.routes import Route

from agent.src.handlers.specific_course import handle_specific_course
from agent.src.handlers.topic_recommendation import handle_topic_recommendation
from agent.src.handlers.next_step import handle_next_step
from agent.src.handlers.recommendation_explanation import handle_recommendation_explanation

def process_question(user: UserContext, number_question: int, question: str, llm_client,
                        entity_extractor, router, pre_gates, post_gates, generation_gates, response_generator, course_repository, course_access_gate, logger,
                        context: ConversationContext | None = None):
    request = AgentRequest(
        message=question,
        user=user,
        context=context or ConversationContext(),
    )

    trace = TraceContext(
        number_question=number_question,
        question=request.message,
        logger=logger,
    )

    # Entity extraction
    request.entities = entity_extractor.extract(message=request.message)

    trace.log_entities(request.entities)

    trace.log_llm_call(purpose="entity_extraction", model=llm_client.safe_model_uri)

    # Routing
    route_decision = router.detect(
        message=request.message,
        entities=request.entities,
        context=request.context,
    )
    request.route = route_decision.route

    trace.log_route(
        route=route_decision.route,
        source=route_decision.source,
        confidence=route_decision.confidence,
    )

    if route_decision.source == "llm":
        trace.log_llm_call(purpose="route_detection", model=llm_client.safe_model_uri,)

    # Pre-gates
    pre_gate_result = pre_gates.check(request)

    for result in pre_gate_result.results:
        trace.log_gate(
            name=result.gate or "unknown",
            allowed=result.allowed,
            reason=result.reason,
        )

    if not pre_gate_result.allowed:
        failed_gate = pre_gate_result.results[-1]

        trace.finish_blocked(reason_code=(failed_gate.gate or "pre_gate_failed"))

        return trace.trace

    # Route handling
    if request.route == Route.SPECIFIC_COURSE:
        return handle_specific_course(
            request=request,
            trace=trace,
            course_repository=course_repository,
            course_access_gate=course_access_gate,
            response_generator=response_generator,
            llm_client=llm_client,
            post_gates=post_gates,
            generation_gates=generation_gates,
        )

    if request.route == Route.CONCEPT_EXPLANATION:
        answer = response_generator.generate(
            message=request.message,
            route=request.route,
            entities=request.entities,
        )

        trace.log_llm_call(
            purpose="concept_explanation_response_generation",
            model=llm_client.safe_model_uri,
            input_summary={
                "route": request.route.value,
            },
        )

        trace.trace.used_course_ids = []

        trace.finish_success(
            user_message=answer,
            reason_code="concept_explanation_generated",
        )

        return trace.trace

    if request.route == Route.TOPIC_RECOMMENDATION:
        return handle_topic_recommendation(
            request=request,
            trace=trace,
            course_repository=course_repository,
            response_generator=response_generator,
            llm_client=llm_client,
            post_gates=post_gates,
            generation_gates=generation_gates,
        )

    if request.route == Route.NEXT_STEP:
        return handle_next_step(
            request=request,
            trace=trace,
            course_repository=course_repository,
            response_generator=response_generator,
            llm_client=llm_client,
            post_gates=post_gates,
            generation_gates=generation_gates,
        )

    if request.route == Route.RECOMMENDATION_EXPLANATION:
        return handle_recommendation_explanation(
            request=request,
            trace=trace,
            course_repository=course_repository,
            response_generator=response_generator,
            post_gates=post_gates,
            generation_gates=generation_gates,
        )

    trace.finish_blocked(reason_code="unsupported_route")

    return trace.trace
