from typing import Literal

from pydantic import BaseModel, Field


class ConversationContext(BaseModel):
    pending_action: str | None = None
    pending_course_name: str | None = None
    pending_course_source: Literal["stepik", "university"] | None = None
    recommended_course_ids: list[int] = Field(default_factory=list)
    recommendation_question: str | None = None
    recommendation_answer: str | None = None

class RecommendationResult(BaseModel):
    selected_course_ids: list[int] = Field(min_length=1, max_length=5)
    answer: str

class AgentResponse(BaseModel):
    answer: str
    route: str | None = None
    course_ids: list[int] = Field(default_factory=list)
