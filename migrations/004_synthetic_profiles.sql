ALTER TABLE users ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS users_synthetic_profiles_idx
    ON users (is_synthetic, name) WHERE is_synthetic;

DO $$
DECLARE
    university_value integer;
    year_2025_value integer;
    year_2026_value integer;
    first_half_value integer;
    second_half_value integer;
    group_value integer;
    database_subject_value integer;
    algorithms_subject_value integer;
    anna_value integer;
    dmitry_value integer;
    elena_value integer;
BEGIN
    SELECT id INTO university_value FROM universities WHERE name = 'Тестовый университет' ORDER BY id LIMIT 1;
    SELECT id INTO year_2025_value FROM academic_years WHERE start_year = 2025;
    SELECT id INTO year_2026_value FROM academic_years WHERE start_year = 2026;
    SELECT id INTO first_half_value FROM polugodies WHERE number = 1;
    SELECT id INTO second_half_value FROM polugodies WHERE number = 2;
    SELECT id INTO group_value FROM student_groups
        WHERE university_id = university_value AND name = 'ТЕСТ-101';
    SELECT id INTO database_subject_value FROM university_subjects
        WHERE university_id = university_value AND name = 'Базы данных';
    SELECT id INTO algorithms_subject_value FROM university_subjects
        WHERE university_id = university_value AND name = 'Алгоритмы и структуры данных';

    UPDATE users SET
        name = 'Анна Смирнова',
        interests = 'SQL, аналитика данных и визуализация',
        goal = 'Стать аналитиком данных',
        experience = 'Начальный Python и уверенный Excel',
        study_year = 2,
        university_id = university_value,
        max_user_id = NULL,
        is_synthetic = true,
        registration_completed_at = now(),
        updated_at = now()
    WHERE phone = '+79000000011'
    RETURNING id INTO anna_value;

    UPDATE users SET
        name = 'Дмитрий Волков',
        interests = 'Алгоритмы, backend и базы данных',
        goal = 'Стать backend-разработчиком',
        experience = 'Python, Git и основы SQL',
        study_year = 2,
        university_id = university_value,
        max_user_id = NULL,
        is_synthetic = true,
        registration_completed_at = now(),
        updated_at = now()
    WHERE phone = '+79000000012'
    RETURNING id INTO dmitry_value;

    INSERT INTO users(
        name, university_id, phone, role, interests, study_year, goal, experience,
        preferences, registration_completed_at, updated_at, is_synthetic
    ) VALUES (
        'Елена Кузнецова', university_value, '+79000000013', 'student',
        'Проектирование ПО, алгоритмы и командная разработка', 2,
        'Стать системным аналитиком', 'Основы Java, UML и реляционных баз данных',
        '{}'::jsonb, now(), now(), true
    )
    ON CONFLICT (phone) WHERE phone IS NOT NULL DO UPDATE SET
        name = EXCLUDED.name,
        university_id = EXCLUDED.university_id,
        interests = EXCLUDED.interests,
        study_year = EXCLUDED.study_year,
        goal = EXCLUDED.goal,
        experience = EXCLUDED.experience,
        max_user_id = NULL,
        is_synthetic = true,
        registration_completed_at = now(),
        updated_at = now()
    RETURNING id INTO elena_value;

    INSERT INTO user_subject_results(user_id, subject_id, academic_year_id, polugodie_id, grade)
    VALUES
        (anna_value, database_subject_value, year_2025_value, second_half_value, '5'),
        (anna_value, algorithms_subject_value, year_2025_value, first_half_value, 'зачёт'),
        (dmitry_value, database_subject_value, year_2025_value, second_half_value, '4'),
        (dmitry_value, algorithms_subject_value, year_2025_value, first_half_value, '5'),
        (elena_value, database_subject_value, year_2025_value, second_half_value, '5'),
        (elena_value, algorithms_subject_value, year_2025_value, first_half_value, '4')
    ON CONFLICT (user_id, subject_id, academic_year_id, polugodie_id)
    DO UPDATE SET grade = EXCLUDED.grade;

    INSERT INTO user_group_memberships(user_id, group_id, academic_year_id)
    VALUES
        (anna_value, group_value, year_2026_value),
        (dmitry_value, group_value, year_2026_value),
        (elena_value, group_value, year_2026_value)
    ON CONFLICT (user_id, group_id, academic_year_id) DO NOTHING;
END $$;
