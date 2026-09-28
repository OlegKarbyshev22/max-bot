CREATE TABLE IF NOT EXISTS specialties (
    id serial PRIMARY KEY,
    name text NOT NULL,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    faculty_id integer NOT NULL,
    department_id integer,
    UNIQUE (university_id, faculty_id, name),
    UNIQUE (id, university_id),
    FOREIGN KEY (faculty_id, university_id)
        REFERENCES faculties(id, university_id) ON DELETE RESTRICT,
    FOREIGN KEY (department_id, university_id)
        REFERENCES departments(id, university_id) ON DELETE RESTRICT
);

ALTER TABLE student_groups ADD COLUMN IF NOT EXISTS specialty_id integer;
ALTER TABLE users ADD COLUMN IF NOT EXISTS faculty_id integer;
ALTER TABLE users ADD COLUMN IF NOT EXISTS specialty_id integer;
ALTER TABLE users ADD COLUMN IF NOT EXISTS group_id integer;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'student_groups_specialty_id_fkey') THEN
        ALTER TABLE student_groups ADD CONSTRAINT student_groups_specialty_id_fkey
            FOREIGN KEY (specialty_id) REFERENCES specialties(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_faculty_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_faculty_id_fkey
            FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_specialty_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_specialty_id_fkey
            FOREIGN KEY (specialty_id) REFERENCES specialties(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_group_id_fkey') THEN
        ALTER TABLE users ADD CONSTRAINT users_group_id_fkey
            FOREIGN KEY (group_id) REFERENCES student_groups(id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS user_learning_stages (
    id bigserial PRIMARY KEY,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id integer REFERENCES course_registry(id) ON DELETE SET NULL,
    stage_type text NOT NULL CHECK (
        stage_type IN ('planned', 'started', 'milestone', 'completed', 'paused')
    ),
    title text NOT NULL CHECK (NULLIF(BTRIM(title), '') IS NOT NULL),
    details text NOT NULL DEFAULT '',
    occurred_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS specialties_faculty_idx ON specialties(faculty_id, name);
CREATE INDEX IF NOT EXISTS student_groups_specialty_idx ON student_groups(specialty_id, name);
CREATE INDEX IF NOT EXISTS users_education_profile_idx
    ON users(university_id, faculty_id, specialty_id, group_id);
CREATE INDEX IF NOT EXISTS user_learning_stages_history_idx
    ON user_learning_stages(user_id, occurred_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS user_learning_stages_course_idx
    ON user_learning_stages(course_id) WHERE course_id IS NOT NULL;

DO $$
DECLARE
    university_value integer;
    faculty_value integer;
    department_value integer;
    specialty_value integer;
    group_value integer;
BEGIN
    SELECT id INTO university_value
    FROM universities WHERE name = 'Тестовый университет' ORDER BY id LIMIT 1;

    IF university_value IS NOT NULL THEN
        SELECT id INTO faculty_value FROM faculties
        WHERE university_id = university_value
        ORDER BY id LIMIT 1;
        SELECT id INTO department_value FROM departments
        WHERE university_id = university_value
        ORDER BY id LIMIT 1;

        IF faculty_value IS NOT NULL THEN
            INSERT INTO specialties(name, university_id, faculty_id, department_id)
            VALUES (
                'Программная инженерия', university_value, faculty_value, department_value
            )
            ON CONFLICT (university_id, faculty_id, name) DO UPDATE
            SET department_id = EXCLUDED.department_id
            RETURNING id INTO specialty_value;

            SELECT id INTO group_value FROM student_groups
            WHERE university_id = university_value AND name = 'ТЕСТ-101';

            UPDATE student_groups SET specialty_id = specialty_value
            WHERE id = group_value;

            UPDATE users SET
                faculty_id = faculty_value,
                specialty_id = specialty_value,
                group_id = group_value
            WHERE university_id = university_value AND is_synthetic;
        END IF;
    END IF;
END $$;

-- Заполняем новые поля у уже активированных профилей. Такие пользователи могли
-- быть скопированы из синтетического шаблона до появления этих колонок, но их
-- членство в учебной группе уже было сохранено.
WITH latest_membership AS (
    SELECT DISTINCT ON (membership.user_id)
        membership.user_id,
        membership.group_id
    FROM user_group_memberships membership
    JOIN academic_years academic_year ON academic_year.id = membership.academic_year_id
    ORDER BY membership.user_id, academic_year.start_year DESC, membership.id DESC
)
UPDATE users profile
SET group_id = COALESCE(profile.group_id, student_group.id),
    faculty_id = COALESCE(profile.faculty_id, student_group.faculty_id),
    specialty_id = COALESCE(profile.specialty_id, student_group.specialty_id),
    updated_at = now()
FROM latest_membership
JOIN student_groups student_group ON student_group.id = latest_membership.group_id
WHERE profile.id = latest_membership.user_id
  AND (
      profile.group_id IS NULL
      OR profile.faculty_id IS NULL
      OR profile.specialty_id IS NULL
  );

-- Шаблоны пересобираются из fixture-статусов: старый этап «начат» не должен
-- пережить смену демо-курса на «в плане».
DELETE FROM user_learning_stages stage
USING users profile
WHERE stage.user_id = profile.id
  AND profile.is_synthetic;

INSERT INTO user_learning_stages(user_id, course_id, stage_type, title, details, occurred_at)
SELECT
    user_course.user_id,
    user_course.course_id,
    CASE user_course.status
        WHEN 'completed' THEN 'completed'
        WHEN 'in_progress' THEN 'started'
        ELSE 'planned'
    END,
    CASE user_course.status
        WHEN 'completed' THEN 'Курс завершён'
        WHEN 'in_progress' THEN 'Курс начат'
        ELSE 'Курс добавлен в план'
    END,
    '',
    user_course.selected_at
FROM user_courses user_course
JOIN users profile ON profile.id = user_course.user_id AND profile.is_synthetic
JOIN course_registry registry ON registry.id = user_course.course_id
LEFT JOIN stepik_courses stepik ON stepik.id = registry.stepik_course_id
LEFT JOIN university_courses university_course ON university_course.id = registry.university_course_id
WHERE NOT EXISTS (
    SELECT 1 FROM user_learning_stages stage
    WHERE stage.user_id = user_course.user_id
      AND stage.course_id = user_course.course_id
      AND stage.stage_type = CASE user_course.status
          WHEN 'completed' THEN 'completed'
          WHEN 'in_progress' THEN 'started'
          ELSE 'planned'
      END
);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO maxbot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO maxbot;
