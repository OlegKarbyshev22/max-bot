-- Демонстрационные профили, отображаемые в выборе входа MAX-бота.
-- Миграция идемпотентна: её можно применять после обновления проекта.
DO $$
DECLARE
    university_value integer;
    faculty_value integer;
    department_value integer;
    moais_specialty_value integer;
    applied_specialty_value integer;
    moais_group_value integer;
    applied_group_value integer;
    year_2025_value integer;
    year_2026_value integer;
    first_half_value integer;
    second_half_value integer;
    database_subject_value integer;
    algorithms_subject_value integer;
    oleg_value integer;
    zlata_value integer;
    timur_value integer;
BEGIN
    SELECT id INTO university_value FROM universities WHERE name = 'Тестовый университет' ORDER BY id LIMIT 1;
    IF university_value IS NULL THEN RAISE EXCEPTION 'Fixture university is missing'; END IF;
    SELECT id INTO faculty_value FROM faculties WHERE university_id = university_value ORDER BY id LIMIT 1;
    UPDATE faculties SET name = 'ФМИАТ' WHERE id = faculty_value;
    SELECT id INTO department_value FROM departments WHERE university_id = university_value ORDER BY id LIMIT 1;

    INSERT INTO specialties(name, university_id, faculty_id, department_id)
    VALUES ('Математическое обеспечение и администрирование информационных систем', university_value, faculty_value, department_value)
    ON CONFLICT (university_id, faculty_id, name) DO UPDATE SET department_id = EXCLUDED.department_id
    RETURNING id INTO moais_specialty_value;
    INSERT INTO specialties(name, university_id, faculty_id, department_id)
    VALUES ('Прикладная информатика', university_value, faculty_value, department_value)
    ON CONFLICT (university_id, faculty_id, name) DO UPDATE SET department_id = EXCLUDED.department_id
    RETURNING id INTO applied_specialty_value;

    SELECT id INTO moais_group_value FROM student_groups WHERE university_id = university_value AND name = 'ТЕСТ-101';
    UPDATE student_groups SET faculty_id = faculty_value, specialty_id = moais_specialty_value WHERE id = moais_group_value;
    INSERT INTO student_groups(name, university_id, faculty_id, department_id, specialty_id)
    VALUES ('ПИ-21', university_value, faculty_value, department_value, applied_specialty_value)
    ON CONFLICT (university_id, name) DO UPDATE SET faculty_id = EXCLUDED.faculty_id, department_id = EXCLUDED.department_id, specialty_id = EXCLUDED.specialty_id
    RETURNING id INTO applied_group_value;
    INSERT INTO schedule_group_links(schedule_entry_id, group_id)
    SELECT schedule_entry_id, applied_group_value
    FROM schedule_group_links
    WHERE group_id = moais_group_value
    ON CONFLICT (schedule_entry_id, group_id) DO NOTHING;

    SELECT id INTO year_2025_value FROM academic_years WHERE start_year = 2025;
    SELECT id INTO year_2026_value FROM academic_years WHERE start_year = 2026;
    SELECT id INTO first_half_value FROM polugodies WHERE number = 1;
    SELECT id INTO second_half_value FROM polugodies WHERE number = 2;
    SELECT id INTO database_subject_value FROM university_subjects WHERE university_id = university_value AND name = 'Базы данных';
    SELECT id INTO algorithms_subject_value FROM university_subjects WHERE university_id = university_value AND name = 'Алгоритмы и структуры данных';

    UPDATE users SET
        name = 'Карбышев Олег', university_id = university_value, faculty_id = faculty_value, specialty_id = moais_specialty_value, group_id = moais_group_value,
        interests = 'Python, SQL, анализ данных и AI', goal = 'Развиваться в разработке и анализе данных', experience = 'Python, основы SQL и Git',
        study_year = 2, max_user_id = NULL, is_synthetic = true, registration_completed_at = now(), updated_at = now()
    WHERE phone = '+79000000011' RETURNING id INTO oleg_value;
    UPDATE users SET
        name = 'Юрьева Злата', university_id = university_value, faculty_id = faculty_value, specialty_id = moais_specialty_value, group_id = moais_group_value,
        interests = 'Алгоритмы, backend-разработка и базы данных', goal = 'Стать backend-разработчиком', experience = 'Python, Git и основы SQL',
        study_year = 2, max_user_id = NULL, is_synthetic = true, registration_completed_at = now(), updated_at = now()
    WHERE phone = '+79000000012' RETURNING id INTO zlata_value;
    UPDATE users SET
        name = 'Тимур Гиззятов', university_id = university_value, faculty_id = faculty_value, specialty_id = applied_specialty_value, group_id = applied_group_value,
        interests = 'Проектирование ПО, веб-разработка и машинное обучение', goal = 'Стать прикладным разработчиком', experience = 'Основы Java, UML и реляционных баз данных',
        study_year = 2, max_user_id = NULL, is_synthetic = true, registration_completed_at = now(), updated_at = now()
    WHERE phone = '+79000000013' RETURNING id INTO timur_value;

    DELETE FROM user_group_memberships WHERE user_id IN (oleg_value, zlata_value, timur_value);
    INSERT INTO user_group_memberships(user_id, group_id, academic_year_id) VALUES
        (oleg_value, moais_group_value, year_2026_value), (zlata_value, moais_group_value, year_2026_value), (timur_value, applied_group_value, year_2026_value)
    ON CONFLICT (user_id, group_id, academic_year_id) DO NOTHING;
    INSERT INTO user_subject_results(user_id, subject_id, academic_year_id, polugodie_id, grade) VALUES
        (oleg_value, database_subject_value, year_2025_value, second_half_value, '5'), (oleg_value, algorithms_subject_value, year_2025_value, first_half_value, 'зачёт'),
        (zlata_value, database_subject_value, year_2025_value, second_half_value, '4'), (zlata_value, algorithms_subject_value, year_2025_value, first_half_value, '5'),
        (timur_value, database_subject_value, year_2025_value, second_half_value, '5'), (timur_value, algorithms_subject_value, year_2025_value, first_half_value, '4')
    ON CONFLICT (user_id, subject_id, academic_year_id, polugodie_id) DO UPDATE SET grade = EXCLUDED.grade;
END $$;
