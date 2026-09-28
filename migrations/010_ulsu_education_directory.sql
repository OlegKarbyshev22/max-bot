-- Минимальный учебный справочник для регистрации студентов УлГУ.
DO $$
DECLARE
    university_value integer;
    faculty_value integer;
    department_value integer;
    moais_specialty_value integer;
    applied_specialty_value integer;
BEGIN
    SELECT id INTO university_value FROM universities WHERE name = 'УлГУ' ORDER BY id LIMIT 1;
    IF university_value IS NULL THEN
        RETURN;
    END IF;

    INSERT INTO faculties(name, university_id)
    VALUES ('ФМИАТ', university_value)
    ON CONFLICT (university_id, name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id INTO faculty_value;

    INSERT INTO departments(name, university_id)
    VALUES ('Кафедра информационных технологий', university_value)
    ON CONFLICT (university_id, name) DO UPDATE SET name = EXCLUDED.name
    RETURNING id INTO department_value;

    INSERT INTO specialties(name, university_id, faculty_id, department_id)
    VALUES ('Математическое обеспечение и администрирование информационных систем', university_value, faculty_value, department_value)
    ON CONFLICT (university_id, faculty_id, name) DO UPDATE SET department_id = EXCLUDED.department_id
    RETURNING id INTO moais_specialty_value;

    INSERT INTO specialties(name, university_id, faculty_id, department_id)
    VALUES ('Прикладная информатика', university_value, faculty_value, department_value)
    ON CONFLICT (university_id, faculty_id, name) DO UPDATE SET department_id = EXCLUDED.department_id
    RETURNING id INTO applied_specialty_value;

    INSERT INTO student_groups(name, university_id, faculty_id, department_id, specialty_id)
    VALUES
        ('МОАИС-21', university_value, faculty_value, department_value, moais_specialty_value),
        ('МОАИС-23/1', university_value, faculty_value, department_value, moais_specialty_value),
        ('ПИ-21', university_value, faculty_value, department_value, applied_specialty_value)
    ON CONFLICT (university_id, name) DO UPDATE
    SET faculty_id = EXCLUDED.faculty_id, department_id = EXCLUDED.department_id,
        specialty_id = EXCLUDED.specialty_id;
END $$;
