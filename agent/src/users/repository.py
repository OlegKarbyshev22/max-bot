from agent.src.db.connection import get_db_connection
# входной user_id  - это users.max_user_id
class UserRepository:

    def get_by_max_user_id(self, user_id: str):
        query = """
            SELECT
                id,
                max_user_id,
                university_id,
                interests,
                goal,
                experience,
                role
            FROM users
            WHERE max_user_id = %s;
        """

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (user_id,))
                return cursor.fetchone()

    def get_user_course_ids(self, db_user_id: int) -> dict[str, list[int]]:
        query = """
            SELECT
                user_course.course_id,
                user_course.status
            FROM user_courses AS user_course
            JOIN users AS profile ON profile.id = user_course.user_id
            WHERE user_course.user_id = %s
              -- После повторной регистрации старая история не является историей
              -- нового профиля. Это защищает агента от старых демо-данных.
              AND (
                  profile.registration_completed_at IS NULL
                  OR user_course.selected_at >= profile.registration_completed_at
              );
        """

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (db_user_id,))
                rows = cursor.fetchall()

        result = {"completed": [], "in_progress": [], "selected": [],}

        for row in rows:
            status = row["status"]

            if status in result:
                result[status].append(row["course_id"])

        return result

    def get_academic_results(self, db_user_id: int) -> list[dict]:
        query = """
            SELECT
                subject.name AS subject,
                result.grade,
                COALESCE(result.semester_number, half.number) AS semester_number
            FROM user_subject_results AS result
            JOIN university_subjects AS subject ON subject.id = result.subject_id
            JOIN polugodies AS half ON half.id = result.polugodie_id
            WHERE result.user_id = %s
            ORDER BY COALESCE(result.semester_number, half.number) DESC, subject.name
        """
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (db_user_id,))
                return cursor.fetchall()
