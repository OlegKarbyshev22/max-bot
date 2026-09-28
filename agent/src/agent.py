from agent.src.users.repository import UserRepository
from agent.src.users.service import build_user_context

from agent.src.entities.extractor import EntityExtractor
from agent.src.llm.builder import build_llm_client
from agent.src.routing.llm_router import LLMRouter
from agent.src.routing.router import Router
from agent.src.generation.generator import ResponseGenerator

from agent.src.config.loader import (load_roles_config, load_routes_config)
from agent.src.gates.pre.pipeline import PreGatePipeline
from agent.src.gates.post.pipeline import PostGatePipeline
from agent.src.gates.pre.required_entities import RequiredEntitiesGate
from agent.src.gates.pre.role_allowed import RoleAllowedGate
from agent.src.gates.pre.route_enabled import RouteEnabledGate
from agent.src.gates.pre.permission_check import PermissionCheckGate
from agent.src.gates.pre.course_access_gate import CourseAccessGate
from agent.src.gates.pre.user_interests_present import UserInterestsPresentGate
from agent.src.gates.post.grounded_course_response import GroundedCourseResponseGate
from agent.src.gates.post.no_internal_details import NoInternalDetailsGate
from agent.src.gates.post.response_not_empty import ResponseNotEmptyGate
from agent.src.gates.post.pipeline import PostGatePipeline
from agent.src.gates.post.no_completed_courses import NoCompletedCoursesGate
from agent.src.gates.post.grounded_recommendation import GroundedRecommendationGate
from agent.src.gates.post.university_priority import UniversityPriorityGate
from agent.src.gates.post.no_user_courses_recommended import NoUserCoursesRecommendedGate
from agent.src.gates.pre_generation.candidate_fields_present import CandidateFieldsPresentGate
from agent.src.gates.pre_generation.course_candidates_present import CourseCandidatesPresentGate
from agent.src.gates.pre_generation.next_step_context_ready import NextStepContextReadyGate
from agent.src.gates.pre_generation.pipeline import GenerationGatePipeline


from agent.src.logging.logger import AgentLogger

from agent.src.courses.repository import CourseRepository

from agent.src.process_question import process_question

from agent.src.models import AgentResponse, ConversationContext


class CourseAgent:
    def __init__(self):
        self.routes_config = load_routes_config()
        self.roles_config = load_roles_config()

        self.llm_client = build_llm_client()

        self.entity_extractor = EntityExtractor(llm_client=self.llm_client,)

        self.router = Router(llm_router=LLMRouter(llm_client=self.llm_client,),)

        self.response_generator = ResponseGenerator(llm_client=self.llm_client,)

        self.course_repository = CourseRepository()
        self.user_repository = UserRepository()

        self.course_access_gate = CourseAccessGate()

        self.pre_gates = PreGatePipeline(
            routes_config=self.routes_config,
            gates=[
                RouteEnabledGate(routes_config=self.routes_config,),
                RoleAllowedGate(roles_config=self.roles_config,),
                PermissionCheckGate(roles_config=self.roles_config, routes_config=self.routes_config,),
                RequiredEntitiesGate(routes_config=self.routes_config,),
                UserInterestsPresentGate(),
            ],
        )

        self.post_gates = PostGatePipeline(
            routes_config=self.routes_config,
            gates=[
                ResponseNotEmptyGate(),
                NoInternalDetailsGate(),
                NoCompletedCoursesGate(),
                NoUserCoursesRecommendedGate(),
                UniversityPriorityGate(),
                GroundedCourseResponseGate(),
                GroundedRecommendationGate(),
            ],
        )

        self.generation_pre_gates = GenerationGatePipeline(
            gates=[
                CourseCandidatesPresentGate(),
                CandidateFieldsPresentGate(),
                NextStepContextReadyGate(),
            ],
        )

        self.logger = AgentLogger()

    def ask_with_metadata(
        self,
        user_id: str,
        question: str,
        conversation_context: dict | ConversationContext | None = None,
    ) -> AgentResponse:

        user_context = build_user_context(user_id=user_id, user_repository=self.user_repository,)

        context = (
            conversation_context
            if isinstance(conversation_context, ConversationContext)
            else ConversationContext.model_validate(conversation_context or {})
        )

        trace = process_question(
            number_question=1,
            question=question,
            user=user_context,
            llm_client=self.llm_client,
            entity_extractor=self.entity_extractor,
            router=self.router,
            pre_gates=self.pre_gates,
            post_gates=self.post_gates,
            response_generator=self.response_generator,
            course_repository=self.course_repository,
            course_access_gate=self.course_access_gate,
            logger=self.logger,
            generation_gates=self.generation_pre_gates,
            context=context,
        )

        self.logger.save_batch([trace])

        answer = (trace.outcome.user_message or "Не удалось обработать запрос.")

        return AgentResponse(
            answer=answer,
            route=trace.route,
            course_ids=trace.used_course_ids,
        )
