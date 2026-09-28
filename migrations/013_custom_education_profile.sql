ALTER TABLE users
    ADD COLUMN IF NOT EXISTS custom_university_name text,
    ADD COLUMN IF NOT EXISTS custom_faculty_name text,
    ADD COLUMN IF NOT EXISTS custom_specialty_name text;
