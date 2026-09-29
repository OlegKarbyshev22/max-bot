import json
from typing import Any

from agent.src.db.connection import get_db_connection


class BotRepository:
    def get_user(self, max_user_id: str) -> dict[str, Any] | None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.*, un.name AS university_name,
                       faculty.name AS faculty_name,
                       specialty.name AS specialty_name,
                       student_group.name AS group_name
                FROM users u
                LEFT JOIN universities un ON un.id = u.university_id
                LEFT JOIN faculties faculty ON faculty.id = u.faculty_id
                LEFT JOIN specialties specialty ON specialty.id = u.specialty_id
                LEFT JOIN student_groups student_group ON student_group.id = u.group_id
                WHERE u.max_user_id = %s
                """,
                (max_user_id,),
            )
            return cursor.fetchone()

    def is_registered(self, max_user_id: str) -> bool:
        user = self.get_user(max_user_id)
        return bool(user and user.get("registration_completed_at"))

    def authenticate_by_phone(self, max_user_id: str, phone: str) -> dict[str, Any] | None:
        """Find a completed profile by verified phone and bind it to this MAX account."""
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, max_user_id, registration_completed_at
                FROM users WHERE phone = %s AND NOT is_synthetic FOR UPDATE
                """,
                (phone,),
            )
            user = cursor.fetchone()
            if not user:
                cursor.execute(
                    "SELECT id, phone, registration_completed_at FROM users WHERE max_user_id = %s FOR UPDATE",
                    (max_user_id,),
                )
                existing_max_user = cursor.fetchone()
                if not existing_max_user:
                    return None
                if existing_max_user.get("phone") not in {None, phone}:
                    raise ValueError("This MAX account is already linked to another phone")
                cursor.execute(
                    "UPDATE users SET phone = %s, updated_at = now() WHERE id = %s RETURNING *",
                    (phone, existing_max_user["id"]),
                )
                return cursor.fetchone()
            cursor.execute(
                "SELECT id, phone FROM users WHERE max_user_id = %s AND id <> %s FOR UPDATE",
                (max_user_id, user["id"]),
            )
            conflicting_user = cursor.fetchone()
            if conflicting_user:
                raise ValueError("This MAX account is already linked to another phone")
            cursor.execute(
                "UPDATE users SET max_user_id = %s, updated_at = now() WHERE id = %s RETURNING *",
                (max_user_id, user["id"]),
            )
            return cursor.fetchone()

    def list_synthetic_profiles(self) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.name, u.study_year,
                       COALESCE(un.name, u.custom_university_name) AS university_name,
                       (u.university_id IS NULL AND u.custom_university_name IS NOT NULL)
                           AS is_external_university,
                       faculty.name AS faculty_name, specialty.name AS specialty_name,
                       student_group.name AS group_name
                FROM users u
                LEFT JOIN universities un ON un.id = u.university_id
                LEFT JOIN faculties faculty ON faculty.id = u.faculty_id
                LEFT JOIN specialties specialty ON specialty.id = u.specialty_id
                LEFT JOIN student_groups student_group ON student_group.id = u.group_id
                WHERE u.is_synthetic
                ORDER BY u.name
                """
            )
            return cursor.fetchall()

    def activate_synthetic_profile(
        self, max_user_id: str, phone: str, synthetic_user_id: int
    ) -> dict[str, Any]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE id = %s AND is_synthetic FOR UPDATE",
                (synthetic_user_id,),
            )
            template = cursor.fetchone()
            if not template:
                raise ValueError("Synthetic profile was not found")
            cursor.execute(
                "SELECT id, phone FROM users WHERE max_user_id = %s FOR UPDATE",
                (max_user_id,),
            )
            current_user = cursor.fetchone()
            if current_user and current_user.get("phone") not in {None, phone}:
                raise ValueError("This MAX account is already linked to another phone")
            cursor.execute(
                "SELECT id FROM users WHERE phone = %s AND NOT is_synthetic FOR UPDATE",
                (phone,),
            )
            phone_user = cursor.fetchone()
            if phone_user and (not current_user or phone_user["id"] != current_user["id"]):
                raise ValueError("This phone is already linked to another user")

            cursor.execute(
                """
                INSERT INTO users(
                    name, email, university_id, faculty_id, specialty_id, group_id,
                    max_user_id, phone, role, interests, study_year, goal, experience,
                    custom_university_name, custom_faculty_name, custom_specialty_name,
                    preferences, registration_completed_at, updated_at, is_synthetic
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now(),false)
                ON CONFLICT (max_user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    email = EXCLUDED.email,
                    university_id = EXCLUDED.university_id,
                    faculty_id = EXCLUDED.faculty_id,
                    specialty_id = EXCLUDED.specialty_id,
                    group_id = EXCLUDED.group_id,
                    phone = EXCLUDED.phone,
                    role = EXCLUDED.role,
                    interests = EXCLUDED.interests,
                    study_year = EXCLUDED.study_year,
                    goal = EXCLUDED.goal,
                    experience = EXCLUDED.experience,
                    custom_university_name = EXCLUDED.custom_university_name,
                    custom_faculty_name = EXCLUDED.custom_faculty_name,
                    custom_specialty_name = EXCLUDED.custom_specialty_name,
                    preferences = EXCLUDED.preferences,
                    registration_completed_at = now(),
                    updated_at = now(),
                    is_synthetic = false
                RETURNING *
                """,
                (
                    template["name"], template.get("email"), template.get("university_id"),
                    template.get("faculty_id"), template.get("specialty_id"), template.get("group_id"),
                    max_user_id, phone, template.get("role") or "student",
                    template.get("interests") or "", template.get("study_year"),
                    template.get("goal") or "", template.get("experience") or "",
                    template.get("custom_university_name"), template.get("custom_faculty_name"),
                    template.get("custom_specialty_name"),
                    json.dumps(template.get("preferences") or {}, ensure_ascii=False),
                ),
            )
            user = cursor.fetchone()
            cursor.execute("DELETE FROM user_subject_results WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_group_memberships WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_courses WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_learning_stages WHERE user_id = %s", (user["id"],))
            cursor.execute(
                """
                INSERT INTO user_subject_results(
                    user_id, subject_id, academic_year_id, polugodie_id, grade
                )
                SELECT %s, subject_id, academic_year_id, polugodie_id, grade
                FROM user_subject_results WHERE user_id = %s
                """,
                (user["id"], template["id"]),
            )
            cursor.execute(
                """
                INSERT INTO user_group_memberships(user_id, group_id, academic_year_id)
                SELECT %s, group_id, academic_year_id
                FROM user_group_memberships WHERE user_id = %s
                """,
                (user["id"], template["id"]),
            )
            cursor.execute(
                """
                INSERT INTO user_courses(user_id, course_id, status, selected_at)
                SELECT %s, course_id, status, now()
                FROM user_courses WHERE user_id = %s
                """,
                (user["id"], template["id"]),
            )
            cursor.execute(
                """
                INSERT INTO user_learning_stages(
                    user_id, course_id, stage_type, title, details, occurred_at,
                    progress_percent
                )
                SELECT %s, course_id, stage_type, title, details, occurred_at,
                       progress_percent
                FROM user_learning_stages WHERE user_id = %s
                """,
                (user["id"], template["id"]),
            )
            return user

    def get_session(self, max_user_id: str) -> dict[str, Any] | None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT * FROM bot_sessions WHERE max_user_id = %s", (max_user_id,))
            return cursor.fetchone()

    def set_session(self, max_user_id: str, state: str, data: dict[str, Any] | None = None) -> None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO bot_sessions(max_user_id, state, data, updated_at)
                VALUES (%s, %s, %s::jsonb, now())
                ON CONFLICT (max_user_id) DO UPDATE
                SET state = EXCLUDED.state, data = EXCLUDED.data, updated_at = now()
                """,
                (max_user_id, state, json.dumps(data or {}, ensure_ascii=False)),
            )

    def update_session_data(self, max_user_id: str, state: str, **values: Any) -> None:
        session = self.get_session(max_user_id) or {"data": {}}
        data = dict(session.get("data") or {})
        data.update(values)
        self.set_session(max_user_id, state, data)

    def reset_registration(self, max_user_id: str) -> None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET registration_completed_at = NULL, updated_at = now() WHERE max_user_id = %s",
                (max_user_id,),
            )
        # Повторная регистрация начинается с новой верификации номера.
        self.set_session(max_user_id, "wait_phone", {})

    def update_profile_field(self, max_user_id: str, field: str, value: str) -> None:
        if field not in {"goal", "experience"}:
            raise ValueError("Only goal and experience can be edited")
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE users SET {field} = %s, updated_at = now() WHERE max_user_id = %s RETURNING id",
                (value, max_user_id),
            )
            if not cursor.fetchone():
                raise ValueError("User is not registered")

    def complete_registration(self, max_user_id: str) -> dict[str, Any]:
        session = self.get_session(max_user_id)
        if not session:
            raise ValueError("Registration session is missing")
        data = session.get("data") or {}
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users(
                    name, university_id, faculty_id, specialty_id, group_id,
                    max_user_id, phone, role, interests, study_year,
                    goal, experience, custom_university_name, custom_faculty_name, custom_specialty_name,
                    preferences, registration_completed_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'student', %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb, now(), now())
                ON CONFLICT (max_user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    university_id = EXCLUDED.university_id,
                    faculty_id = EXCLUDED.faculty_id,
                    specialty_id = EXCLUDED.specialty_id,
                    group_id = EXCLUDED.group_id,
                    phone = EXCLUDED.phone,
                    interests = EXCLUDED.interests,
                    study_year = EXCLUDED.study_year,
                    goal = EXCLUDED.goal,
                    experience = EXCLUDED.experience,
                    custom_university_name = EXCLUDED.custom_university_name,
                    custom_faculty_name = EXCLUDED.custom_faculty_name,
                    custom_specialty_name = EXCLUDED.custom_specialty_name,
                    registration_completed_at = now(),
                    updated_at = now()
                RETURNING *
                """,
                (
                    data["name"],
                    data.get("university_id"),
                    data.get("faculty_id"),
                    data.get("specialty_id"),
                    data.get("group_id"),
                    max_user_id,
                    data["phone"],
                    data["goal"],
                    data["study_year"],
                    data["goal"],
                    data["experience"],
                    data.get("custom_university_name"),
                    data.get("custom_faculty_name"),
                    data.get("custom_specialty_name"),
                ),
            )
            user = cursor.fetchone()
            # Самостоятельная регистрация может идти после демо-профиля или
            # перезапуска анкеты. Его учебные данные нельзя переносить в новый
            # профиль: иначе агент считает чужие курсы знаниями пользователя.
            cursor.execute("DELETE FROM user_learning_stages WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_courses WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_subject_results WHERE user_id = %s", (user["id"],))
            cursor.execute("DELETE FROM user_group_memberships WHERE user_id = %s", (user["id"],))
            if data.get("group_id"):
                cursor.execute(
                    """
                    INSERT INTO academic_years(start_year, end_year)
                    VALUES (
                        CASE WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 9
                             THEN EXTRACT(YEAR FROM CURRENT_DATE)::integer
                             ELSE EXTRACT(YEAR FROM CURRENT_DATE)::integer - 1 END,
                        CASE WHEN EXTRACT(MONTH FROM CURRENT_DATE) >= 9
                             THEN EXTRACT(YEAR FROM CURRENT_DATE)::integer + 1
                             ELSE EXTRACT(YEAR FROM CURRENT_DATE)::integer END
                    )
                    ON CONFLICT (start_year, end_year) DO UPDATE SET start_year = EXCLUDED.start_year
                    RETURNING id
                    """
                )
                academic_year_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO user_group_memberships(user_id, group_id, academic_year_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, group_id, academic_year_id) DO NOTHING
                    """,
                    (user["id"], data["group_id"], academic_year_id),
                )
        self.set_session(max_user_id, "ready", {})
        return user

    def list_universities(self) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, name FROM universities
                WHERE NULLIF(BTRIM(name), '') IS NOT NULL
                  AND name <> 'Тестовый университет'
                ORDER BY name
            """)
            return cursor.fetchall()

    def list_faculties(self, university_id: int) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name
                FROM faculties
                WHERE university_id = %s
                  AND name <> 'Факультет математики, информационных и авиационных технологий'
                ORDER BY name
                """,
                (university_id,),
            )
            return cursor.fetchall()

    def list_specialties(self, university_id: int, faculty_id: int) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name FROM specialties
                WHERE university_id = %s AND faculty_id = %s ORDER BY name
                """,
                (university_id, faculty_id),
            )
            return cursor.fetchall()

    def list_student_groups(
        self, university_id: int, faculty_id: int, specialty_id: int
    ) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name FROM student_groups
                WHERE university_id = %s AND faculty_id = %s AND specialty_id = %s
                ORDER BY name
                """,
                (university_id, faculty_id, specialty_id),
            )
            return cursor.fetchall()

    def list_history(self, max_user_id: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT uc.course_id, uc.status, cr.source,
                       COALESCE(sc.name, c.course_name) AS name,
                       COALESCE(sc.url, '') AS url,
                       COALESCE(
                           progress.progress_percent,
                           CASE uc.status WHEN 'completed' THEN 100 ELSE 0 END
                       ) AS progress_percent,
                       progress.stage_type AS latest_stage_type
                FROM users u
                JOIN user_courses uc ON uc.user_id = u.id
                JOIN course_registry cr ON cr.id = uc.course_id
                LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
                LEFT JOIN university_courses c ON c.id = cr.university_course_id
                LEFT JOIN LATERAL (
                    SELECT stage.progress_percent, stage.stage_type
                    FROM user_learning_stages stage
                    WHERE stage.user_id = u.id AND stage.course_id = uc.course_id
                    ORDER BY stage.occurred_at DESC, stage.id DESC
                    LIMIT 1
                ) progress ON true
                WHERE u.max_user_id = %s
                  AND (
                      u.registration_completed_at IS NULL
                      OR uc.selected_at >= u.registration_completed_at
                  )
                ORDER BY cr.source, uc.selected_at DESC, name
                """,
                (max_user_id,),
            )
            return cursor.fetchall()

    def list_academic_history(self, max_user_id: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT subject.name, year.start_year, year.end_year,
                       half.number AS polugodie,
                       COALESCE(result.semester_number, half.number) AS semester_number,
                       result.grade
                FROM users u
                JOIN user_subject_results result ON result.user_id = u.id
                JOIN university_subjects subject ON subject.id = result.subject_id
                JOIN academic_years year ON year.id = result.academic_year_id
                JOIN polugodies half ON half.id = result.polugodie_id
                WHERE u.max_user_id = %s
                ORDER BY year.start_year DESC, half.number DESC, subject.name
                """,
                (max_user_id,),
            )
            return cursor.fetchall()

    def list_learning_stages(self, max_user_id: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT stage.id, stage.stage_type, stage.title, stage.details,
                       stage.progress_percent,
                       stage.occurred_at,
                       COALESCE(stepik.name, university_course.course_name) AS course_name
                FROM users profile
                JOIN user_learning_stages stage ON stage.user_id = profile.id
                LEFT JOIN course_registry registry ON registry.id = stage.course_id
                LEFT JOIN stepik_courses stepik ON stepik.id = registry.stepik_course_id
                LEFT JOIN university_courses university_course
                    ON university_course.id = registry.university_course_id
                WHERE profile.max_user_id = %s
                ORDER BY stage.occurred_at DESC, stage.id DESC
                """,
                (max_user_id,),
            )
            return cursor.fetchall()

    def list_progress_courses(self, max_user_id: str) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT history.course_id, history.source, history.name,
                       history.status, history.progress_percent
                FROM (
                    SELECT uc.course_id, cr.source,
                           COALESCE(stepik.name, university_course.course_name) AS name,
                           uc.status,
                           COALESCE(
                               progress.progress_percent,
                               CASE uc.status WHEN 'completed' THEN 100 ELSE 0 END
                           ) AS progress_percent,
                           uc.selected_at
                    FROM users profile
                    JOIN user_courses uc ON uc.user_id = profile.id
                    JOIN course_registry cr ON cr.id = uc.course_id
                    LEFT JOIN stepik_courses stepik ON stepik.id = cr.stepik_course_id
                    LEFT JOIN university_courses university_course
                        ON university_course.id = cr.university_course_id
                    LEFT JOIN LATERAL (
                        SELECT stage.progress_percent
                        FROM user_learning_stages stage
                        WHERE stage.user_id = profile.id AND stage.course_id = uc.course_id
                        ORDER BY stage.occurred_at DESC, stage.id DESC
                        LIMIT 1
                    ) progress ON true
                    WHERE profile.max_user_id = %s
                      AND uc.status IN ('selected', 'in_progress')
                      AND (
                          profile.registration_completed_at IS NULL
                          OR uc.selected_at >= profile.registration_completed_at
                      )
                ) history
                ORDER BY history.source, history.selected_at DESC, history.name
                """,
                (max_user_id,),
            )
            return cursor.fetchall()

    def remove_course_from_plan(self, max_user_id: str, course_id: int) -> None:
        """Remove an unfinished course and its progress events from a user's plan."""
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT profile.id AS user_id, user_course.status
                FROM users profile
                JOIN user_courses user_course ON user_course.user_id = profile.id
                WHERE profile.max_user_id = %s AND user_course.course_id = %s
                FOR UPDATE OF user_course
                """,
                (max_user_id, course_id),
            )
            item = cursor.fetchone()
            if not item:
                raise ValueError("Course is not in the user's learning plan")
            if item["status"] == "completed":
                raise ValueError("Completed courses cannot be removed from learning history")
            cursor.execute(
                "DELETE FROM user_learning_stages WHERE user_id = %s AND course_id = %s",
                (item["user_id"], course_id),
            )
            cursor.execute(
                "DELETE FROM user_courses WHERE user_id = %s AND course_id = %s",
                (item["user_id"], course_id),
            )

    def record_course_progress(
        self,
        max_user_id: str,
        course_id: int,
        progress_percent: int | None = None,
        paused: bool = False,
    ) -> None:
        if paused and progress_percent is not None:
            raise ValueError("Paused progress must not include a new percentage")
        if not paused and progress_percent not in {0, 25, 50, 75, 100}:
            raise ValueError("Unsupported course progress")
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT profile.id AS user_id, user_course.status,
                       COALESCE(latest.progress_percent, 0) AS current_progress
                FROM users profile
                JOIN user_courses user_course ON user_course.user_id = profile.id
                LEFT JOIN LATERAL (
                    SELECT stage.progress_percent
                    FROM user_learning_stages stage
                    WHERE stage.user_id = profile.id AND stage.course_id = user_course.course_id
                    ORDER BY stage.occurred_at DESC, stage.id DESC
                    LIMIT 1
                ) latest ON true
                WHERE profile.max_user_id = %s AND user_course.course_id = %s
                FOR UPDATE OF user_course
                """,
                (max_user_id, course_id),
            )
            item = cursor.fetchone()
            if not item:
                raise ValueError("Course is not in the user's learning plan")
            if item["status"] == "completed":
                raise ValueError("Completed course progress cannot be changed")

            if paused:
                stage_type = "paused"
                title = "Обучение приостановлено"
                stored_progress = item["current_progress"]
                new_status = item["status"]
            else:
                stored_progress = progress_percent
                if progress_percent == 0:
                    stage_type, title, new_status = "planned", "Добавлен в план", "selected"
                elif progress_percent == 100:
                    stage_type, title, new_status = "completed", "Курс завершён", "completed"
                else:
                    stage_type = "started" if progress_percent == 25 else "milestone"
                    title = f"Пройдено {progress_percent}%"
                    new_status = "in_progress"

            cursor.execute(
                """
                UPDATE user_courses SET status = %s, selected_at = now()
                WHERE user_id = %s AND course_id = %s
                """,
                (new_status, item["user_id"], course_id),
            )
            cursor.execute(
                """
                INSERT INTO user_learning_stages(
                    user_id, course_id, stage_type, title, progress_percent
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (item["user_id"], course_id, stage_type, title, stored_progress),
            )

    def list_schedule(
        self, max_user_id: str, academic_start_year: int, polugodie: int
    ) -> list[dict[str, Any]]:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT entry.id, entry.day_of_week, entry.start_time, entry.end_time,
                       entry.lesson_type, subject.name AS subject_name,
                       teacher.name AS teacher_name, building.name AS building_name,
                       classroom.room_number
                FROM users u
                JOIN user_group_memberships membership ON membership.user_id = u.id
                JOIN academic_years membership_year ON membership_year.id = membership.academic_year_id
                JOIN schedule_group_links link ON link.group_id = membership.group_id
                JOIN schedule_entries entry ON entry.id = link.schedule_entry_id
                JOIN academic_years entry_year ON entry_year.id = entry.academic_year_id
                JOIN polugodies half ON half.id = entry.polugodie_id
                JOIN university_subjects subject ON subject.id = entry.subject_id
                JOIN teachers teacher ON teacher.id = entry.teacher_id
                JOIN classrooms classroom ON classroom.id = entry.classroom_id
                JOIN buildings building ON building.id = classroom.building_id
                WHERE u.max_user_id = %s
                  AND membership_year.start_year = %s
                  AND entry_year.start_year = %s
                  AND half.number = %s
                ORDER BY entry.day_of_week, entry.start_time, subject.name
                """,
                (max_user_id, academic_start_year, academic_start_year, polugodie),
            )
            return cursor.fetchall()

    def search_courses(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        pattern = f"%{query}%"
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cr.id, cr.source, COALESCE(sc.name, uc.course_name) AS name
                FROM course_registry cr
                LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
                LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
                WHERE COALESCE(sc.name, uc.course_name) ILIKE %s
                ORDER BY
                    CASE WHEN LOWER(COALESCE(sc.name, uc.course_name)) = LOWER(%s) THEN 0 ELSE 1 END,
                    LENGTH(COALESCE(sc.name, uc.course_name))
                LIMIT %s
                """,
                (pattern, query, limit),
            )
            return cursor.fetchall()

    def get_courses(self, course_ids: list[int]) -> list[dict[str, Any]]:
        if not course_ids:
            return []
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT cr.id, cr.source, COALESCE(sc.name, uc.course_name) AS name
                FROM course_registry cr
                LEFT JOIN stepik_courses sc ON sc.id = cr.stepik_course_id
                LEFT JOIN university_courses uc ON uc.id = cr.university_course_id
                WHERE cr.id = ANY(%s)
                ORDER BY array_position(%s::integer[], cr.id)
                """,
                (course_ids, course_ids),
            )
            return cursor.fetchall()

    def set_course_status(self, max_user_id: str, course_id: int, status: str) -> None:
        if status not in {"completed", "in_progress", "selected"}:
            raise ValueError("Unsupported course status")
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE max_user_id = %s", (max_user_id,))
            user = cursor.fetchone()
            if not user:
                raise ValueError("User is not registered")
            cursor.execute(
                """
                INSERT INTO user_courses(user_id, course_id, status, selected_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (user_id, course_id) DO UPDATE
                SET status = EXCLUDED.status, selected_at = now()
                """,
                (user["id"], course_id, status),
            )
            stage_types = {
                "selected": ("planned", "Курс добавлен в план", 0),
                "in_progress": ("started", "Курс начат", 0),
                "completed": ("completed", "Курс завершён", 100),
            }
            stage_type, title, progress_percent = stage_types[status]
            cursor.execute(
                """
                INSERT INTO user_learning_stages(
                    user_id, course_id, stage_type, title, details, progress_percent
                )
                SELECT %s, registry.id, %s, %s, '', %s
                FROM course_registry registry
                WHERE registry.id = %s
                """,
                (user["id"], stage_type, title, progress_percent, course_id),
            )

    def log_message(
        self,
        max_user_id: str,
        role: str,
        content: str,
        route: str | None = None,
        course_ids: list[int] | None = None,
    ) -> None:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO conversation_log(user_id, max_user_id, role, content, route, course_ids)
                SELECT id, %s, %s, %s, %s, %s FROM users WHERE max_user_id = %s
                """,
                (max_user_id, role, content, route, course_ids or [], max_user_id),
            )
