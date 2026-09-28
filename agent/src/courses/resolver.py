import json

from agent.src.courses.models import SimilarCourseSelection


class CourseResolver:
    def __init__(self, repository, llm_client):
        self.repository = repository
        self.llm_client = llm_client

    def find_exact(self, course_name: str):
        return self.repository.find_exact_by_name(course_name)