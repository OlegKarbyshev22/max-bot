import logging
import re

import httpx

from agent.settings import ENABLE_VECTOR_SEARCH
from agent.src.courses.models import CourseData, UserCourseSummary
from agent.src.db.connection import get_db_connection
from agent.src.embeddings.client import EmbeddingClient, vector_literal


COURSE_FIELDS = """
    cr.id,
    cr.source,
    cr.source_course_id,
    COALESCE(sc.name, uc.course_name) AS name,
    COALESCE(sc.description, uc.description) AS description,
    sc.learning_outcomes,
    sc.requirements,
    sc.program_text,
    sc.level,
    uc.themes,
    uc.concepts,
    uc.faculty,
    uc.department,
    uc.format,
    uc.complexity_score,
    uc.university_id,
    sc.url
"""
MIN_VECTOR_SIMILARITY = 0.45


class CourseRepository:
    def __init__(self, embedding_client: EmbeddingClient | None = None):
        self.embedding_client = embedding_client or EmbeddingClient()

    def find_exact_by_name(self, course_name: str) -> list[CourseData]:
        # A user often omits punctuation ("DevOps Junior" vs "DevOps: Junior")
        # or makes a small typo.  Search all meaningful title words and use pg_trgm
        # similarity as a last resort instead of requiring an exact title string.
        tokens = [token for token in re.findall(r"[^\W_]+", course_name.lower()) if len(token) >= 2]
        token_clause = " AND ".join(
            "COALESCE(sc.name, uc.course_name) ILIKE %s" for _ in tokens
        ) or "FALSE"
        query = f"""
            SELECT {COURSE_FIELDS}
            FROM course_registry cr
            LEFT JOIN stepik_courses sc ON cr.stepik_course_id = sc.id
            LEFT JOIN university_courses uc ON cr.university_course_id = uc.id
            WHERE LOWER(COALESCE(sc.name, uc.course_name)) = LOWER(%s)
               OR COALESCE(sc.name, uc.course_name) ILIKE %s
               OR ({token_clause})
               OR similarity(LOWER(COALESCE(sc.name, uc.course_name)), LOWER(%s)) >= 0.35
            ORDER BY CASE
                WHEN LOWER(COALESCE(sc.name, uc.course_name)) = LOWER(%s) THEN 0 ELSE 1
            END,
            similarity(LOWER(COALESCE(sc.name, uc.course_name)), LOWER(%s)) DESC,
            LENGTH(COALESCE(sc.name, uc.course_name))
            LIMIT 5
        """
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                query,
                [course_name, f"%{course_name}%"]
                + [f"%{token}%" for token in tokens]
                + [course_name, course_name, course_name],
            )
            rows = cursor.fetchall()
        return [CourseData.model_validate(row) for row in rows]

    def get_by_registry_ids(self, course_ids: list[int]) -> list[CourseData]:
        if not course_ids:
            return []
        query = f"""
            SELECT {COURSE_FIELDS}
            FROM course_registry cr
            LEFT JOIN stepik_courses sc ON cr.stepik_course_id = sc.id
            LEFT JOIN university_courses uc ON cr.university_course_id = uc.id
            WHERE cr.id = ANY(%s)
            ORDER BY array_position(%s::integer[], cr.id)
        """
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, (course_ids, course_ids))
            rows = cursor.fetchall()
        return [CourseData.model_validate(row) for row in rows]

    def list_course_names_by_source(self, source: str) -> list[dict]:
        if source not in {"stepik", "university"}:
            raise ValueError(f"Unsupported source: {source}")
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cr.id, COALESCE(sc.name, uc.course_name) AS name
                FROM course_registry cr
                LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
                LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
                WHERE cr.source = %s AND COALESCE(sc.name, uc.course_name) IS NOT NULL
                ORDER BY name
                """,
                (source,),
            )
            return cursor.fetchall()

    def get_courses_by_registry_ids(self, course_ids: list[int]) -> list[UserCourseSummary]:
        if not course_ids:
            return []
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cr.id, cr.source,
                       COALESCE(sc.name, uc.course_name) AS name,
                       COALESCE(sc.description, uc.description) AS description,
                       sc.level, uc.complexity_score
                FROM course_registry cr
                LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
                LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
                WHERE cr.id = ANY(%s)
                ORDER BY cr.id
                """,
                (course_ids,),
            )
            rows = cursor.fetchall()
        return [UserCourseSummary.model_validate(row) for row in rows]

    def _query_embedding(self, topics: list[str]) -> str | None:
        if not ENABLE_VECTOR_SEARCH:
            return None
        try:
            return vector_literal(self.embedding_client.embed_query(", ".join(topics)))
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as error:
            logging.warning("Vector search unavailable, using lexical fallback: %s", error)
            return None

    def _find_by_topics(
        self,
        source: str,
        topics: list[str],
        university_id: int | None,
        excluded_course_ids: list[int],
        limit: int,
    ) -> list[CourseData]:
        if not topics or (source == "university" and university_id is None):
            return []
        embedding = self._query_embedding(topics)
        university_clause = "AND uc.university_id = %s" if source == "university" else ""
        lexical = """
            EXISTS (
                SELECT 1 FROM unnest(%s::text[]) AS q(topic)
                WHERE COALESCE(sc.name, uc.course_name, '') ILIKE '%%' || q.topic || '%%'
                   OR COALESCE(sc.keywords, uc.keywords, '') ILIKE '%%' || q.topic || '%%'
                   OR COALESCE(uc.themes, '') ILIKE '%%' || q.topic || '%%'
                   OR COALESCE(uc.concepts, '') ILIKE '%%' || q.topic || '%%'
                   OR EXISTS (
                       SELECT 1 FROM course_topics ct2
                       JOIN topics t2 ON t2.id = ct2.topic_id
                       WHERE ct2.course_id = cr.id AND t2.name ILIKE '%%' || q.topic || '%%'
                   )
            )
        """
        query = f"""
            SELECT {COURSE_FIELDS},
                   (CASE WHEN {lexical} THEN 1.0 ELSE 0.0 END) +
                   (CASE WHEN %s::text IS NOT NULL AND ce.embedding IS NOT NULL
                         THEN (1.0 - (ce.embedding <=> CAST(%s AS vector))) * 2.0
                         ELSE 0.0 END) AS relevance
            FROM course_registry cr
            LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
            LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
            LEFT JOIN course_embeddings ce ON ce.course_id = cr.id
            WHERE cr.source = %s
              {university_clause}
              AND NOT (cr.id = ANY(%s))
              AND (
                    {lexical}
                    OR (
                        %s::text IS NOT NULL
                        AND ce.embedding IS NOT NULL
                        AND 1.0 - (ce.embedding <=> CAST(%s AS vector)) >= %s
                    )
              )
            ORDER BY relevance DESC, cr.id
            LIMIT %s
        """
        params: list = [topics, embedding, embedding, source]
        if source == "university":
            params.append(university_id)
        params.extend(
            [excluded_course_ids, topics, embedding, embedding, MIN_VECTOR_SIMILARITY, limit]
        )
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [CourseData.model_validate(row) for row in rows]

    def find_university_courses_by_topics(
        self,
        topics: list[str],
        university_id: int | None,
        excluded_course_ids: list[int] | None = None,
        limit: int = 20,
    ) -> list[CourseData]:
        return self._find_by_topics(
            "university", topics, university_id, excluded_course_ids or [], limit
        )

    def find_stepik_courses_by_topics(
        self,
        topics: list[str],
        excluded_course_ids: list[int] | None = None,
        limit: int = 20,
    ) -> list[CourseData]:
        return self._find_by_topics("stepik", topics, None, excluded_course_ids or [], limit)

    def get_topics_by_course_ids(self, course_ids: list[int]) -> list[str]:
        if not course_ids:
            return []
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT t.name
                FROM course_topics ct
                JOIN topics t ON t.id = ct.topic_id
                WHERE ct.course_id = ANY(%s)
                ORDER BY t.name
                """,
                (course_ids,),
            )
            return [row["name"] for row in cursor.fetchall()]
