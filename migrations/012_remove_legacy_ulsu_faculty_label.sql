-- Older local databases can contain a duplicate long label with dependent
-- specialties. Keep it intact for referential safety; registration lists hide it.
SELECT 1;
