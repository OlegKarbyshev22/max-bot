DO $$
DECLARE
    anna_value integer;
    dmitry_value integer;
    elena_value integer;
BEGIN
    SELECT id INTO anna_value FROM users WHERE phone = '+79000000011' AND is_synthetic;
    SELECT id INTO dmitry_value FROM users WHERE phone = '+79000000012' AND is_synthetic;
    SELECT id INTO elena_value FROM users WHERE phone = '+79000000013' AND is_synthetic;

    DELETE FROM user_courses WHERE user_id IN (anna_value, dmitry_value, elena_value);

    INSERT INTO user_courses(user_id, course_id, status, selected_at)
    SELECT fixture.user_id, fixture.course_id, fixture.status, now()
    FROM (VALUES
        (anna_value, 425, 'selected'),
        (anna_value, 3, 'selected'),
        (dmitry_value, 1210, 'selected'),
        (dmitry_value, 133, 'completed'),
        (elena_value, 19, 'completed'),
        (elena_value, 8961, 'selected')
    ) AS fixture(user_id, course_id, status)
    JOIN course_registry registry ON registry.id = fixture.course_id
    WHERE fixture.user_id IS NOT NULL
    ON CONFLICT (user_id, course_id) DO UPDATE SET
        status = EXCLUDED.status,
        selected_at = EXCLUDED.selected_at;
END $$;
