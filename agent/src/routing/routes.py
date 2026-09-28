from enum import Enum

class Route(str, Enum):
    TOPIC_RECOMMENDATION = "topic_recommendation"
    SPECIFIC_COURSE = "specific_course"
    CONCEPT_EXPLANATION = "concept_explanation"
    NEXT_STEP = "next_step"
    RECOMMENDATION_EXPLANATION = "recommendation_explanation"
    UNKNOWN = "unknown"
