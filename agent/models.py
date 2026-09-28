from pydantic import BaseModel, Field

from agent.src.entities.models import LlmEntityCandidates
from agent.src.routing.routes import Route
from agent.src.models import ConversationContext
from agent.src.logging.models import AgentTrace

class ProcessResult(BaseModel):
    trace: AgentTrace
    context: ConversationContext


class AcademicResult(BaseModel):
    subject: str
    grade: str
    semester_number: int | None = None


class UserContext(BaseModel):
    user_id: str
    role: str
    university_id: int | None = None

    interests: str
    goal: str = ""
    experience: str = ""

    completed_course_ids: list[int] = Field(default_factory=list)
    current_course_ids: list[int] = Field(default_factory=list)
    selected_course_ids: list[int] = Field(default_factory=list)
    academic_results: list[AcademicResult] = Field(default_factory=list)

    preferences: dict = Field(default_factory=dict)


class AgentRequest(BaseModel):
    message: str
    user: UserContext

    entities: LlmEntityCandidates | None = None
    route: Route | None = None

    context: ConversationContext = Field(default_factory=ConversationContext)
