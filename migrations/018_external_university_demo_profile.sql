-- Демонстрационный профиль студента стороннего вуза. Отсутствующий university_id
-- не даёт ему доступ к внутренним курсам УлГУ; доступны общие курсы Stepik.
INSERT INTO users(
    name, email, university_id, faculty_id, specialty_id, group_id,
    max_user_id, phone, role, interests, study_year, goal, experience,
    custom_university_name, custom_faculty_name, custom_specialty_name,
    preferences, registration_completed_at, updated_at, is_synthetic
) VALUES (
    'Алина Соколова', NULL, NULL, NULL, NULL, NULL,
    NULL, '+79000000014', 'student',
    'Веб-разработка, Python и базы данных', 2,
    'Научиться создавать backend для веб-приложений',
    'Начальный Python, HTML и CSS',
    'Казанский федеральный университет',
    'Институт информационных технологий и интеллектуальных систем',
    'Программная инженерия',
    '{}'::jsonb, now(), now(), true
)
ON CONFLICT (phone) WHERE phone IS NOT NULL DO UPDATE SET
    name = EXCLUDED.name,
    email = EXCLUDED.email,
    university_id = NULL,
    faculty_id = NULL,
    specialty_id = NULL,
    group_id = NULL,
    max_user_id = NULL,
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
    is_synthetic = true;
