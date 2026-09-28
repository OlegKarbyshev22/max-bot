from typing import Optional
from pydantic import BaseModel, Field

class LlmEntityCandidates(BaseModel):
    course_names: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)