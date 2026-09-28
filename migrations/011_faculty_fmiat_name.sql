-- Use the faculty's established short name in profiles and registration lists.
UPDATE faculties
SET name = 'ФМИАТ'
WHERE name = 'Факультет математики, информационных и авиационных технологий'
  AND NOT EXISTS (
      SELECT 1
      FROM faculties same_university
      WHERE same_university.university_id = faculties.university_id
        AND same_university.name = 'ФМИАТ'
  );
