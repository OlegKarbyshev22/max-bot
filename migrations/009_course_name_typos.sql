-- Allows tolerant matching of a course title when a user omits punctuation
-- or makes a minor spelling error.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
