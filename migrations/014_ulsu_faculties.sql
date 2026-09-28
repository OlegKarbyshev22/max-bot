-- Faculties listed by УлГУ for the 2027 admission programme.
DO $$
DECLARE
    university_value integer;
BEGIN
    SELECT id INTO university_value FROM universities WHERE name = 'УлГУ' LIMIT 1;
    IF university_value IS NULL THEN RETURN; END IF;
    INSERT INTO faculties(name, university_id) VALUES
        ('ФМИАТ', university_value),
        ('Инженерно-физический факультет высоких технологий', university_value),
        ('Институт экономики и бизнеса', university_value),
        ('Институт медицины, экологии и физической культуры', university_value),
        ('Факультет лингвистики, межкультурных связей и профессиональной коммуникации', university_value),
        ('Юридический факультет', university_value),
        ('Факультет гуманитарных наук и социальных технологий', university_value),
        ('Факультет культуры и искусства', university_value),
        ('Инзенский филиал УлГУ', university_value),
        ('Заволжский экономико-гуманитарный факультет', university_value)
    ON CONFLICT (university_id, name) DO NOTHING;
END $$;
