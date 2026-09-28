from decimal import Decimal

from pydantic import BaseModel, Field

class CourseData(BaseModel):
    id: int
    source: str
    source_course_id: str

    name: str
    description: str | None = None

    learning_outcomes: str | None = None
    requirements: str | None = None
    program_text: str | None = None
    level: str | None = None

    themes: str | None = None
    concepts: str | None = None

    faculty: str | None = None
    department: str | None = None
    format: str | None = None
    complexity_score: int | None = None

    university_id: int | None = None

    url: str | None = None


class SimilarCourseCandidate(BaseModel):
    course_id: int
    name: str

class SimilarCourseSelection(BaseModel):
    courses: list[SimilarCourseCandidate] = Field(default_factory=list, max_length=5)

class UserCourseSummary(BaseModel):
    id: int
    source: str
    name: str
    description: str | None = None

    level: str | None = None
    complexity_score: int | None = None

class UserLearningContext(BaseModel):
    completed: list[UserCourseSummary] = Field(default_factory=list)
    current: list[UserCourseSummary] = Field(default_factory=list)
    selected: list[UserCourseSummary] = Field(default_factory=list)