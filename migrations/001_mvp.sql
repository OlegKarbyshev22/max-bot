CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE users ADD COLUMN IF NOT EXISTS interests text NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS study_year integer;
ALTER TABLE users ADD COLUMN IF NOT EXISTS goal text NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS experience text NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_completed_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS users_max_user_id_unique
    ON users (max_user_id) WHERE max_user_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS bot_sessions (
    max_user_id text PRIMARY KEY,
    state text NOT NULL,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id bigserial PRIMARY KEY,
    user_id integer REFERENCES users(id) ON DELETE SET NULL,
    max_user_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content text NOT NULL,
    route text,
    course_ids integer[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversation_log_max_user_id_created_idx
    ON conversation_log (max_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS course_embeddings (
    course_id integer PRIMARY KEY REFERENCES course_registry(id) ON DELETE CASCADE,
    document text NOT NULL,
    content_hash text NOT NULL,
    embedding vector(1024) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS course_embeddings_hnsw_idx
    ON course_embeddings USING hnsw (embedding vector_cosine_ops);

GRANT USAGE ON SCHEMA public TO maxbot;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO maxbot;
GRANT MAINTAIN ON ALL TABLES IN SCHEMA public TO maxbot;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO maxbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO maxbot;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO maxbot;
