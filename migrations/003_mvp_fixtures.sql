DO $$
DECLARE
    university_value integer;
    faculty_value integer;
    department_value integer;
    year_2025_value integer;
    year_2026_value integer;
    first_half_value integer;
    second_half_value integer;
    group_value integer;
    database_subject_value integer;
    algorithms_subject_value integer;
    teacher_value integer;
    building_value integer;
    classroom_value integer;
    student_one_value integer;
    student_two_value integer;
    lecture_value integer;
    lab_value integer;
BEGIN
    -- Старые номера фикстур могли совпасть с реальным номером пользователя.
    -- Переносим только служебные записи до создания/обновления шаблонов.
    UPDATE users
    SET phone = CASE phone
        WHEN '+79990000001' THEN '+79000000011'
        WHEN '+79990000002' THEN '+79000000012'
        WHEN '+79990000003' THEN '+79000000013'
    END
    WHERE phone IN ('+79990000001', '+79990000002', '+79990000003')
      AND name IN (
          'Тестовый Студент Один', 'Тестовый Студент Два',
          'Анна Смирнова', 'Дмитрий Волков', 'Елена Кузнецова',
          'Карбышев Олег', 'Юрьева Злата', 'Тимур Гиззятов'
      );

    SELECT id INTO university_value FROM universities WHERE name = 'Тестовый университет' ORDER BY id LIMIT 1;
    IF university_value IS NULL THEN
        INSERT INTO universities(name) VALUES ('Тестовый университет') RETURNING id INTO university_value;
    END IF;

    INSERT INTO faculties(name, university_id) VALUES ('Факультет информационных технологий', university_value)
    ON CONFLICT (university_id, name) DO UPDATE SET name = EXCLUDED.name RETURNING id INTO faculty_value;

    INSERT INTO departments(name, university_id) VALUES ('Кафедра программной инженерии', university_value)
    ON CONFLICT (university_id, name) DO UPDATE SET name = EXCLUDED.name RETURNING id INTO department_value;

    INSERT INTO academic_years(start_year, end_year) VALUES (2025, 2026)
    ON CONFLICT (start_year, end_year) DO UPDATE SET start_year = EXCLUDED.start_year RETURNING id INTO year_2025_value;
    INSERT INTO academic_years(start_year, end_year) VALUES (2026, 2027)
    ON CONFLICT (start_year, end_year) DO UPDATE SET start_year = EXCLUDED.start_year RETURNING id INTO year_2026_value;
    SELECT id INTO first_half_value FROM polugodies WHERE number = 1;
    SELECT id INTO second_half_value FROM polugodies WHERE number = 2;

    INSERT INTO university_subjects(university_id, name, description, department_id, faculty_id)
    VALUES (university_value, 'Базы данных', 'Проектирование и использование реляционных баз данных.', department_value, faculty_value)
    ON CONFLICT (university_id, name) DO UPDATE SET description = EXCLUDED.description
    RETURNING id INTO database_subject_value;

    INSERT INTO university_subjects(university_id, name, description, department_id, faculty_id)
    VALUES (university_value, 'Алгоритмы и структуры данных', 'Базовые алгоритмы и структуры данных.', department_value, faculty_value)
    ON CONFLICT (university_id, name) DO UPDATE SET description = EXCLUDED.description
    RETURNING id INTO algorithms_subject_value;

    INSERT INTO student_groups(name, university_id, faculty_id, department_id)
    VALUES ('ТЕСТ-101', university_value, faculty_value, department_value)
    ON CONFLICT (university_id, name) DO UPDATE SET faculty_id = EXCLUDED.faculty_id
    RETURNING id INTO group_value;

    INSERT INTO teachers(university_id, name, department_id)
    VALUES (university_value, 'Мария Сергеевна Тестова', department_value)
    ON CONFLICT (university_id, department_id, name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id INTO teacher_value;

    INSERT INTO buildings(university_id, name) VALUES (university_value, 'Учебный корпус A')
    ON CONFLICT (university_id, name) DO UPDATE SET name = EXCLUDED.name RETURNING id INTO building_value;
    INSERT INTO classrooms(university_id, building_id, room_number)
    VALUES (university_value, building_value, '301')
    ON CONFLICT (building_id, room_number) DO UPDATE SET university_id = EXCLUDED.university_id
    RETURNING id INTO classroom_value;

    INSERT INTO users(name, university_id, phone, role, interests, study_year, goal, experience,
                      preferences, registration_completed_at, updated_at)
    VALUES ('Тестовый Студент Один', university_value, '+79000000011', 'student', 'SQL и аналитика', 2,
            'Освоить анализ данных', 'Начальный уровень', '{}'::jsonb, now(), now())
    ON CONFLICT (phone) WHERE phone IS NOT NULL DO UPDATE SET
        name = EXCLUDED.name, university_id = EXCLUDED.university_id,
        registration_completed_at = EXCLUDED.registration_completed_at, updated_at = now()
    RETURNING id INTO student_one_value;

    INSERT INTO users(name, university_id, phone, role, interests, study_year, goal, experience,
                      preferences, registration_completed_at, updated_at)
    VALUES ('Тестовый Студент Два', university_value, '+79000000012', 'student', 'Алгоритмы', 2,
            'Улучшить алгоритмическую базу', 'Средний уровень', '{}'::jsonb, now(), now())
    ON CONFLICT (phone) WHERE phone IS NOT NULL DO UPDATE SET
        name = EXCLUDED.name, university_id = EXCLUDED.university_id,
        registration_completed_at = EXCLUDED.registration_completed_at, updated_at = now()
    RETURNING id INTO student_two_value;

    INSERT INTO user_subject_results(user_id, subject_id, academic_year_id, polugodie_id, grade)
    VALUES
        (student_one_value, database_subject_value, year_2025_value, second_half_value, '5'),
        (student_one_value, algorithms_subject_value, year_2025_value, first_half_value, 'зачёт'),
        (student_two_value, database_subject_value, year_2025_value, second_half_value, '4')
    ON CONFLICT (user_id, subject_id, academic_year_id, polugodie_id)
    DO UPDATE SET grade = EXCLUDED.grade;

    INSERT INTO user_group_memberships(user_id, group_id, academic_year_id)
    VALUES (student_one_value, group_value, year_2026_value),
           (student_two_value, group_value, year_2026_value)
    ON CONFLICT (user_id, group_id, academic_year_id) DO NOTHING;

    INSERT INTO schedule_entries(subject_id, teacher_id, classroom_id, day_of_week, start_time,
                                 end_time, lesson_type, academic_year_id, polugodie_id)
    VALUES (database_subject_value, teacher_value, classroom_value, 1, '09:00', '10:30',
            'lecture', year_2026_value, first_half_value)
    ON CONFLICT (subject_id, teacher_id, classroom_id, day_of_week, start_time,
                 academic_year_id, polugodie_id, lesson_type)
    DO UPDATE SET end_time = EXCLUDED.end_time RETURNING id INTO lecture_value;

    INSERT INTO schedule_entries(subject_id, teacher_id, classroom_id, day_of_week, start_time,
                                 end_time, lesson_type, academic_year_id, polugodie_id)
    VALUES (database_subject_value, teacher_value, classroom_value, 3, '10:45', '12:15',
            'lab', year_2026_value, first_half_value)
    ON CONFLICT (subject_id, teacher_id, classroom_id, day_of_week, start_time,
                 academic_year_id, polugodie_id, lesson_type)
    DO UPDATE SET end_time = EXCLUDED.end_time RETURNING id INTO lab_value;

    INSERT INTO schedule_group_links(schedule_entry_id, group_id)
    VALUES (lecture_value, group_value), (lab_value, group_value)
    ON CONFLICT (schedule_entry_id, group_id) DO NOTHING;
END $$;
