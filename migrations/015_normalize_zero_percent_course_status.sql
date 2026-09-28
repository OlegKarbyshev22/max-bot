-- До появления записи прогресса «в процессе» при 0% не имеет смысла:
-- такой курс ещё только добавлен в план. Исправляем старые демо-копии и
-- любые записи, созданные прежней логикой.
WITH zero_progress_courses AS (
    SELECT user_course.user_id, user_course.course_id
    FROM user_courses user_course
    LEFT JOIN LATERAL (
        SELECT stage.progress_percent
        FROM user_learning_stages stage
        WHERE stage.user_id = user_course.user_id
          AND stage.course_id = user_course.course_id
        ORDER BY stage.occurred_at DESC, stage.id DESC
        LIMIT 1
    ) latest_stage ON true
    WHERE user_course.status = 'in_progress'
      AND COALESCE(latest_stage.progress_percent, 0) = 0
), updated_courses AS (
    UPDATE user_courses user_course
    SET status = 'selected', selected_at = now()
    FROM zero_progress_courses course
    WHERE user_course.user_id = course.user_id
      AND user_course.course_id = course.course_id
    RETURNING user_course.user_id, user_course.course_id
)
INSERT INTO user_learning_stages(
    user_id, course_id, stage_type, title, details, occurred_at, progress_percent
)
SELECT user_id, course_id, 'planned', 'Курс добавлен в план', '', now(), 0
FROM updated_courses;
