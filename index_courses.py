import argparse
import hashlib
import logging

from agent.src.db.connection import get_db_connection
from agent.src.embeddings.client import EmbeddingClient, vector_literal


DOCUMENT_LIMIT = 1800


def build_document(row: dict) -> str:
    fields = [
        ("Название", row.get("name"), 250),
        ("Источник", row.get("source"), 30),
        ("Описание", row.get("description"), 500),
        ("Темы", row.get("topics"), 300),
        ("Ключевые слова", row.get("keywords"), 180),
        ("Требования", row.get("requirements"), 220),
        ("Программа", row.get("program_text"), 280),
    ]
    return "\n".join(
        f"{title}: {str(value)[:field_limit]}"
        for title, value, field_limit in fields
        if value
    )[:DOCUMENT_LIMIT]


def fetch_courses(after_id: int, batch_size: int) -> list[dict]:
    with get_db_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT cr.id, cr.source,
                   COALESCE(sc.name, uc.course_name) AS name,
                   COALESCE(sc.description, uc.description) AS description,
                   COALESCE(sc.keywords, uc.keywords) AS keywords,
                   sc.requirements, sc.program_text,
                   STRING_AGG(DISTINCT t.name, ', ') AS topics,
                   ce.content_hash
            FROM course_registry cr
            LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
            LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
            LEFT JOIN course_topics ct ON ct.course_id = cr.id
            LEFT JOIN topics t ON t.id = ct.topic_id
            LEFT JOIN course_embeddings ce ON ce.course_id = cr.id
            WHERE cr.id > %s
            GROUP BY cr.id, sc.name, uc.course_name, sc.description, uc.description,
                     sc.keywords, uc.keywords, sc.requirements, sc.program_text, ce.content_hash
            ORDER BY cr.id
            LIMIT %s
            """,
            (after_id, batch_size),
        )
        return cursor.fetchall()


def index_courses(batch_size: int = 16, limit: int | None = None) -> int:
    client = EmbeddingClient()
    after_id = 0
    indexed = 0
    scanned = 0

    while True:
        rows = fetch_courses(after_id, batch_size)
        if not rows:
            break
        after_id = rows[-1]["id"]
        pending = []
        for row in rows:
            document = build_document(row)
            digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
            if row.get("content_hash") != digest:
                pending.append((row["id"], document, digest))
        if pending:
            embeddings = client.embed(item[1] for item in pending)
            with get_db_connection() as connection, connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO course_embeddings(course_id, document, content_hash, embedding, updated_at)
                    VALUES (%s, %s, %s, %s::vector, now())
                    ON CONFLICT (course_id) DO UPDATE SET
                        document = EXCLUDED.document,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                    """,
                    [
                        (course_id, document, digest, vector_literal(embedding))
                        for (course_id, document, digest), embedding in zip(pending, embeddings)
                    ],
                )
            indexed += len(pending)
        scanned += len(rows)
        logging.info("Scanned %d courses; indexed %d", scanned, indexed)
        if limit and scanned >= limit:
            break
    if limit is None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("ANALYZE course_embeddings")
    return indexed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    print(f"Indexed: {index_courses(args.batch_size, args.limit)}")
