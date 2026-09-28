-- Олег учится в УлГУ, ФМИАТ, группа МОАИС-23/1. Применяем и к шаблону,
-- и к уже созданной из него демонстрационной копии.
DO $$
DECLARE
    ulsu_value integer;
    faculty_value integer;
    department_value integer;
    specialty_value integer;
    group_value integer;
    current_year_value integer;
BEGIN
    SELECT id INTO ulsu_value FROM universities WHERE name = 'УлГУ' ORDER BY id LIMIT 1;
    IF ulsu_value IS NULL THEN
        RAISE EXCEPTION 'УлГУ directory is missing';
    END IF;
    SELECT id INTO faculty_value
    FROM faculties WHERE university_id = ulsu_value AND name = 'ФМИАТ' LIMIT 1;
    SELECT id INTO department_value
    FROM departments WHERE university_id = ulsu_value ORDER BY id LIMIT 1;
    SELECT id INTO specialty_value
    FROM specialties
    WHERE university_id = ulsu_value
      AND faculty_id = faculty_value
      AND name = 'Математическое обеспечение и администрирование информационных систем'
    LIMIT 1;
    SELECT id INTO group_value
    FROM student_groups WHERE university_id = ulsu_value AND name = 'МОАИС-23/1' LIMIT 1;
    SELECT id INTO current_year_value FROM academic_years WHERE start_year = 2026 LIMIT 1;

    -- Копируем учебные дисциплины в каталог УлГУ, затем сохраняем ссылки
    -- в результатах: история остаётся целостной после смены университета.
    INSERT INTO university_subjects(name, university_id, description, department_id, faculty_id)
    SELECT DISTINCT subject.name, ulsu_value, subject.description, department_value, faculty_value
    FROM user_subject_results result
    JOIN users profile ON profile.id = result.user_id
    JOIN university_subjects subject ON subject.id = result.subject_id
    WHERE profile.name = 'Карбышев Олег'
    ON CONFLICT (university_id, name) DO NOTHING;

    UPDATE user_subject_results result
    SET subject_id = ulsu_subject.id
    FROM users profile, university_subjects old_subject, university_subjects ulsu_subject
    WHERE result.user_id = profile.id
      AND profile.name = 'Карбышев Олег'
      AND old_subject.id = result.subject_id
      AND ulsu_subject.university_id = ulsu_value
      AND ulsu_subject.name = old_subject.name;

    UPDATE users
    SET university_id = ulsu_value,
        faculty_id = faculty_value,
        specialty_id = specialty_value,
        group_id = group_value,
        study_year = 4,
        updated_at = now()
    WHERE name = 'Карбышев Олег';

    DELETE FROM user_group_memberships membership
    USING users profile
    WHERE membership.user_id = profile.id AND profile.name = 'Карбышев Олег';

    INSERT INTO user_group_memberships(user_id, group_id, academic_year_id)
    SELECT profile.id, group_value, current_year_value
    FROM users profile
    WHERE profile.name = 'Карбышев Олег'
    ON CONFLICT (user_id, group_id, academic_year_id) DO NOTHING;
END $$;
