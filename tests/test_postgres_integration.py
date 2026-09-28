import os
import unittest
import uuid

import psycopg

from agent.settings import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    require_database_password,
)
from agent.src.db.connection import get_db_connection
from agent.src.users.repository import UserRepository
from agent.src.users.service import build_user_context
from app.db import BotRepository


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "set RUN_DB_TESTS=1")
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.max_user_id = f"integration-{uuid.uuid4()}"
        self.phone = f"+7{uuid.uuid4().int % 10**10:010d}"
        self.repository = BotRepository()

    def tearDown(self) -> None:
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("DELETE FROM bot_sessions WHERE max_user_id=%s", (self.max_user_id,))
            cur.execute("DELETE FROM conversation_log WHERE max_user_id=%s", (self.max_user_id,))
            cur.execute("DELETE FROM users WHERE max_user_id=%s", (self.max_user_id,))
            cur.execute("DELETE FROM users WHERE phone=%s", (self.phone,))

    def test_verified_phone_binds_existing_profile(self) -> None:
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users(name,phone,registration_completed_at)
                VALUES ('Профиль по телефону',%s,now())
                RETURNING id
                """,
                (self.phone,),
            )
            user_id = cur.fetchone()["id"]
        authenticated = self.repository.authenticate_by_phone(self.max_user_id, self.phone)
        self.assertEqual(authenticated["id"], user_id)
        self.assertTrue(self.repository.is_registered(self.max_user_id))

    def test_verified_phone_is_added_to_legacy_max_profile(self) -> None:
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users(name,max_user_id,registration_completed_at)
                VALUES ('Старый профиль без телефона',%s,now())
                RETURNING id
                """,
                (self.max_user_id,),
            )
            user_id = cur.fetchone()["id"]
        authenticated = self.repository.authenticate_by_phone(self.max_user_id, self.phone)
        self.assertEqual(authenticated["id"], user_id)
        self.assertEqual(authenticated["phone"], self.phone)

    def test_synthetic_profile_is_copied_for_new_user(self) -> None:
        profiles = self.repository.list_synthetic_profiles()
        self.assertEqual(len(profiles), 3)
        selected = profiles[0]
        self.repository.activate_synthetic_profile(
            self.max_user_id, self.phone, selected["id"]
        )
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET custom_university_name='Старый ВУЗ',
                    custom_faculty_name='Старый факультет',
                    custom_specialty_name='Старая специальность'
                WHERE max_user_id=%s
                """,
                (self.max_user_id,),
            )
        selected = profiles[1]
        user = self.repository.activate_synthetic_profile(
            self.max_user_id, self.phone, selected["id"]
        )
        self.assertEqual(user["name"], selected["name"])
        self.assertFalse(user["is_synthetic"])
        self.assertIsNone(user["custom_university_name"])
        self.assertIsNone(user["custom_faculty_name"])
        self.assertIsNone(user["custom_specialty_name"])
        self.assertGreater(len(self.repository.list_academic_history(self.max_user_id)), 0)
        self.assertGreater(len(self.repository.list_schedule(self.max_user_id, 2026, 1)), 0)
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT course_id,status FROM user_courses WHERE user_id=%s ORDER BY course_id", (user["id"],))
            copied_courses = cur.fetchall()
            cur.execute("SELECT course_id,status FROM user_courses WHERE user_id=%s ORDER BY course_id", (selected["id"],))
            template_courses = cur.fetchall()
        self.assertEqual(copied_courses, template_courses)
        self.assertEqual(len(copied_courses), 2)
        self.assertEqual(len(self.repository.list_synthetic_profiles()), 3)

    def test_registration_profile_history_and_unique_max_id(self) -> None:
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT id FROM universities WHERE name='Тестовый университет'")
            university_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM faculties WHERE university_id=%s ORDER BY id LIMIT 1", (university_id,))
            faculty_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM specialties WHERE university_id=%s ORDER BY id LIMIT 1", (university_id,))
            specialty_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM student_groups WHERE university_id=%s ORDER BY id LIMIT 1", (university_id,))
            group_id = cur.fetchone()["id"]
        self.repository.set_session(
            self.max_user_id,
            "wait_experience",
            {
                "name": "Тестовый Пользователь",
                "university_id": university_id,
                "faculty_id": faculty_id,
                "specialty_id": specialty_id,
                "group_id": group_id,
                "phone": self.phone,
                "study_year": 2,
                "goal": "SQL и аналитика данных",
                "experience": "Начальный",
            },
        )
        user = self.repository.complete_registration(self.max_user_id)
        self.assertTrue(self.repository.is_registered(self.max_user_id))
        self.assertEqual(user["study_year"], 2)
        profile = self.repository.get_user(self.max_user_id)
        self.assertEqual(profile["faculty_id"], faculty_id)
        self.assertEqual(profile["specialty_id"], specialty_id)
        self.assertEqual(profile["group_id"], group_id)

        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT min(id) AS id FROM course_registry")
            course_id = cur.fetchone()["id"]
        self.repository.set_course_status(self.max_user_id, course_id, "selected")
        self.assertEqual(self.repository.list_history(self.max_user_id)[0]["status"], "selected")
        stages = self.repository.list_learning_stages(self.max_user_id)
        self.assertEqual(stages[0]["stage_type"], "planned")
        self.repository.record_course_progress(self.max_user_id, course_id, progress_percent=50)
        progress = self.repository.list_history(self.max_user_id)[0]
        self.assertEqual(progress["status"], "in_progress")
        self.assertEqual(progress["progress_percent"], 50)

        # Повторная самостоятельная регистрация не должна наследовать курсы
        # от предыдущего (в том числе тестового) профиля.
        self.repository.set_session(
            self.max_user_id,
            "wait_experience",
            {
                "name": "Новый самостоятельный профиль",
                "university_id": university_id,
                "phone": self.phone,
                "study_year": 2,
                "goal": "Теория вероятностей",
                "experience": "Линейная алгебра",
            },
        )
        self.repository.complete_registration(self.max_user_id)
        self.assertEqual(self.repository.list_history(self.max_user_id), [])
        context = build_user_context(self.max_user_id, UserRepository())
        self.assertEqual(context.completed_course_ids, [])
        self.assertEqual(context.current_course_ids, [])
        self.assertEqual(context.selected_course_ids, [])
        self.assertEqual(context.experience, "Линейная алгебра")

        with self.assertRaises(psycopg.errors.UniqueViolation):
            with get_db_connection() as db, db.cursor() as cur:
                cur.execute(
                    "INSERT INTO users(name,max_user_id) VALUES ('duplicate',%s)",
                    (self.max_user_id,),
                )

    def test_academic_history_schedule_and_constraints(self) -> None:
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT id FROM universities WHERE name='Тестовый университет'")
            university_id = cur.fetchone()["id"]
        self.repository.set_session(
            self.max_user_id,
            "wait_experience",
            {
                "name": "Студент Расписания",
                "university_id": university_id,
                "phone": self.phone,
                "study_year": 2,
                "goal": "Проверить расписание",
                "experience": "Начальный",
            },
        )
        user = self.repository.complete_registration(self.max_user_id)

        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT id FROM university_subjects WHERE university_id=%s AND name='Базы данных'", (university_id,))
            subject_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM academic_years WHERE start_year=2025")
            history_year_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM academic_years WHERE start_year=2026")
            schedule_year_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM polugodies WHERE number=2")
            second_half_id = cur.fetchone()["id"]
            cur.execute("SELECT id FROM student_groups WHERE university_id=%s AND name='ТЕСТ-101'", (university_id,))
            group_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO user_subject_results VALUES (%s,%s,%s,%s,'5')",
                (user["id"], subject_id, history_year_id, second_half_id),
            )
            cur.execute(
                "INSERT INTO user_group_memberships(user_id,group_id,academic_year_id) VALUES (%s,%s,%s)",
                (user["id"], group_id, schedule_year_id),
            )

        history = self.repository.list_academic_history(self.max_user_id)
        schedule = self.repository.list_schedule(self.max_user_id, 2026, 1)
        self.assertEqual(history[0]["grade"], "5")
        self.assertTrue(any(item["subject_name"] == "Базы данных" for item in schedule))
        agent_context = build_user_context(self.max_user_id, UserRepository())
        self.assertTrue(
            any(
                item.subject == "Базы данных" and item.grade == "5"
                for item in agent_context.academic_results
            )
        )

        with self.assertRaises(psycopg.errors.UniqueViolation):
            with get_db_connection() as db, db.cursor() as cur:
                cur.execute(
                    "INSERT INTO user_subject_results VALUES (%s,%s,%s,%s,'4')",
                    (user["id"], subject_id, history_year_id, second_half_id),
                )
        with self.assertRaises(psycopg.errors.CheckViolation):
            with get_db_connection() as db, db.cursor() as cur:
                cur.execute("INSERT INTO academic_years(start_year,end_year) VALUES (2090,2092)")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with get_db_connection() as db, db.cursor() as cur:
                cur.execute("INSERT INTO users(name,phone) VALUES ('Дубликат телефона',%s)", (self.phone,))

    def test_vector_insert_and_cosine_search(self) -> None:
        values = [1.0] + [0.0] * 1023
        literal = "[" + ",".join(map(str, values)) + "]"
        with get_db_connection() as db, db.cursor() as cur:
            cur.execute("SELECT max(id) AS id FROM course_registry")
            course_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO course_embeddings(course_id,document,content_hash,embedding)
                VALUES (%s,'integration-vector','integration-vector',%s::vector)
                ON CONFLICT (course_id) DO UPDATE SET embedding=EXCLUDED.embedding
                """,
                (course_id, literal),
            )
            cur.execute(
                "SELECT course_id FROM course_embeddings ORDER BY embedding <=> %s::vector LIMIT 1",
                (literal,),
            )
            self.assertEqual(cur.fetchone()["course_id"], course_id)
            db.rollback()


if __name__ == "__main__":
    unittest.main()
