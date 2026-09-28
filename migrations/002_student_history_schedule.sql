ALTER TABLE users ADD COLUMN IF NOT EXISTS phone text;

CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique
    ON users (phone) WHERE phone IS NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_phone_format_check'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_phone_format_check
            CHECK (phone IS NULL OR phone ~ '^\+[0-9]{10,15}$');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS faculties (
    id serial PRIMARY KEY,
    name text NOT NULL,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    UNIQUE (university_id, name),
    UNIQUE (id, university_id)
);

CREATE TABLE IF NOT EXISTS departments (
    id serial PRIMARY KEY,
    name text NOT NULL,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    UNIQUE (university_id, name),
    UNIQUE (id, university_id)
);

CREATE TABLE IF NOT EXISTS university_subjects (
    id serial PRIMARY KEY,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    name text NOT NULL,
    description text NOT NULL DEFAULT '',
    department_id integer NOT NULL,
    faculty_id integer NOT NULL,
    UNIQUE (university_id, name),
    FOREIGN KEY (department_id, university_id)
        REFERENCES departments(id, university_id) ON DELETE RESTRICT,
    FOREIGN KEY (faculty_id, university_id)
        REFERENCES faculties(id, university_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS academic_years (
    id serial PRIMARY KEY,
    start_year integer NOT NULL,
    end_year integer NOT NULL,
    UNIQUE (start_year, end_year),
    CHECK (start_year BETWEEN 1900 AND 2999),
    CHECK (end_year = start_year + 1)
);

CREATE TABLE IF NOT EXISTS polugodies (
    id serial PRIMARY KEY,
    number smallint NOT NULL UNIQUE CHECK (number IN (1, 2))
);

INSERT INTO polugodies(number) VALUES (1), (2)
ON CONFLICT (number) DO NOTHING;

CREATE TABLE IF NOT EXISTS user_subject_results (
    user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subject_id integer NOT NULL REFERENCES university_subjects(id) ON DELETE RESTRICT,
    academic_year_id integer NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    polugodie_id integer NOT NULL REFERENCES polugodies(id) ON DELETE RESTRICT,
    grade text NOT NULL CHECK (NULLIF(BTRIM(grade), '') IS NOT NULL),
    PRIMARY KEY (user_id, subject_id, academic_year_id, polugodie_id)
);

CREATE TABLE IF NOT EXISTS student_groups (
    id serial PRIMARY KEY,
    name text NOT NULL,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    faculty_id integer NOT NULL,
    department_id integer NOT NULL,
    UNIQUE (university_id, name),
    UNIQUE (id, university_id),
    FOREIGN KEY (faculty_id, university_id)
        REFERENCES faculties(id, university_id) ON DELETE RESTRICT,
    FOREIGN KEY (department_id, university_id)
        REFERENCES departments(id, university_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS user_group_memberships (
    id serial PRIMARY KEY,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id integer NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
    academic_year_id integer NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    UNIQUE (user_id, group_id, academic_year_id)
);

CREATE TABLE IF NOT EXISTS buildings (
    id serial PRIMARY KEY,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    name text NOT NULL,
    UNIQUE (university_id, name),
    UNIQUE (id, university_id)
);

CREATE TABLE IF NOT EXISTS classrooms (
    id serial PRIMARY KEY,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    building_id integer NOT NULL,
    room_number text NOT NULL,
    UNIQUE (building_id, room_number),
    FOREIGN KEY (building_id, university_id)
        REFERENCES buildings(id, university_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS teachers (
    id serial PRIMARY KEY,
    university_id integer NOT NULL REFERENCES universities(id) ON DELETE RESTRICT,
    name text NOT NULL,
    department_id integer NOT NULL,
    UNIQUE (university_id, department_id, name),
    FOREIGN KEY (department_id, university_id)
        REFERENCES departments(id, university_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS schedule_entries (
    id serial PRIMARY KEY,
    subject_id integer NOT NULL REFERENCES university_subjects(id) ON DELETE RESTRICT,
    teacher_id integer NOT NULL REFERENCES teachers(id) ON DELETE RESTRICT,
    classroom_id integer NOT NULL REFERENCES classrooms(id) ON DELETE RESTRICT,
    day_of_week smallint NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    start_time time NOT NULL,
    end_time time NOT NULL,
    lesson_type text NOT NULL CHECK (lesson_type IN ('lecture', 'practice', 'lab', 'seminar')),
    academic_year_id integer NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    polugodie_id integer NOT NULL REFERENCES polugodies(id) ON DELETE RESTRICT,
    CHECK (start_time < end_time),
    UNIQUE (
        subject_id, teacher_id, classroom_id, day_of_week, start_time,
        academic_year_id, polugodie_id, lesson_type
    )
);

CREATE TABLE IF NOT EXISTS schedule_group_links (
    id serial PRIMARY KEY,
    schedule_entry_id integer NOT NULL REFERENCES schedule_entries(id) ON DELETE CASCADE,
    group_id integer NOT NULL REFERENCES student_groups(id) ON DELETE CASCADE,
    UNIQUE (schedule_entry_id, group_id)
);

CREATE OR REPLACE FUNCTION check_schedule_university_consistency()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    subject_university integer;
    teacher_university integer;
    classroom_university integer;
BEGIN
    SELECT university_id INTO subject_university FROM university_subjects WHERE id = NEW.subject_id;
    SELECT university_id INTO teacher_university FROM teachers WHERE id = NEW.teacher_id;
    SELECT university_id INTO classroom_university FROM classrooms WHERE id = NEW.classroom_id;
    IF subject_university IS DISTINCT FROM teacher_university
       OR subject_university IS DISTINCT FROM classroom_university THEN
        RAISE EXCEPTION 'Schedule subject, teacher and classroom must belong to one university';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS schedule_entries_university_check ON schedule_entries;
CREATE TRIGGER schedule_entries_university_check
BEFORE INSERT OR UPDATE ON schedule_entries
FOR EACH ROW EXECUTE FUNCTION check_schedule_university_consistency();

CREATE OR REPLACE FUNCTION check_schedule_group_university_consistency()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    subject_university integer;
    group_university integer;
BEGIN
    SELECT subject.university_id INTO subject_university
    FROM schedule_entries entry
    JOIN university_subjects subject ON subject.id = entry.subject_id
    WHERE entry.id = NEW.schedule_entry_id;
    SELECT university_id INTO group_university FROM student_groups WHERE id = NEW.group_id;
    IF subject_university IS DISTINCT FROM group_university THEN
        RAISE EXCEPTION 'Schedule entry and group must belong to one university';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS schedule_group_links_university_check ON schedule_group_links;
CREATE TRIGGER schedule_group_links_university_check
BEFORE INSERT OR UPDATE ON schedule_group_links
FOR EACH ROW EXECUTE FUNCTION check_schedule_group_university_consistency();

CREATE INDEX IF NOT EXISTS faculties_university_idx ON faculties(university_id);
CREATE INDEX IF NOT EXISTS departments_university_idx ON departments(university_id);
CREATE INDEX IF NOT EXISTS university_subjects_department_idx ON university_subjects(department_id);
CREATE INDEX IF NOT EXISTS university_subjects_faculty_idx ON university_subjects(faculty_id);
CREATE INDEX IF NOT EXISTS user_subject_results_history_idx
    ON user_subject_results(user_id, academic_year_id, polugodie_id);
CREATE INDEX IF NOT EXISTS student_groups_faculty_idx ON student_groups(faculty_id);
CREATE INDEX IF NOT EXISTS student_groups_department_idx ON student_groups(department_id);
CREATE INDEX IF NOT EXISTS user_group_memberships_lookup_idx
    ON user_group_memberships(user_id, academic_year_id, group_id);
CREATE INDEX IF NOT EXISTS classrooms_university_idx ON classrooms(university_id);
CREATE INDEX IF NOT EXISTS teachers_department_idx ON teachers(department_id);
CREATE INDEX IF NOT EXISTS schedule_entries_period_idx
    ON schedule_entries(academic_year_id, polugodie_id, day_of_week, start_time);
CREATE INDEX IF NOT EXISTS schedule_group_links_group_idx ON schedule_group_links(group_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO maxbot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO maxbot;
