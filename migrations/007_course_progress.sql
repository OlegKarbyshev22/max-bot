ALTER TABLE user_learning_stages
    ADD COLUMN IF NOT EXISTS progress_percent smallint;

UPDATE user_learning_stages
SET progress_percent = CASE stage_type
    WHEN 'completed' THEN 100
    WHEN 'planned' THEN 0
    WHEN 'started' THEN 0
    ELSE progress_percent
END
WHERE progress_percent IS NULL;

-- Произвольные этапы без курса больше не используются: прогресс всегда
-- относится к курсу, который пользователь добавил в свой план.
DELETE FROM user_learning_stages WHERE course_id IS NULL;

ALTER TABLE user_learning_stages
    ALTER COLUMN course_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'user_learning_stages_progress_check'
    ) THEN
        ALTER TABLE user_learning_stages
            ADD CONSTRAINT user_learning_stages_progress_check
            CHECK (progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100);
    END IF;
END $$;

ALTER TABLE user_learning_stages
    DROP CONSTRAINT IF EXISTS user_learning_stages_course_id_fkey;
ALTER TABLE user_learning_stages
    ADD CONSTRAINT user_learning_stages_course_id_fkey
    FOREIGN KEY (course_id) REFERENCES course_registry(id) ON DELETE CASCADE;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO maxbot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO maxbot;
