import hashlib
import hmac
import unittest
from datetime import datetime, time
from unittest.mock import AsyncMock, Mock

from agent.src.models import AgentResponse
from bot import (
    MaxBot,
    WAIT_FACULTY,
    WAIT_GOAL,
    WAIT_GROUP,
    WAIT_NAME,
    WAIT_PHONE,
    WAIT_PROFILE_CHOICE,
    WAIT_SPECIALTY,
    WAIT_UNIVERSITY,
    WAIT_YEAR,
    WAIT_EDIT_GOAL,
    WAIT_EDIT_EXPERIENCE,
    WAIT_CUSTOM_UNIVERSITY,
    normalize_phone,
    verified_phone_from_contact,
    split_message,
    format_for_max,
)


class BotHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.repository = Mock()
        self.repository.list_universities.return_value = [{"id": 1, "name": "УлГУ"}]
        self.repository.list_faculties.return_value = [{"id": 10, "name": "ФИСТ"}]
        self.repository.list_specialties.return_value = [
            {"id": 20, "name": "Программная инженерия"}
        ]
        self.repository.list_student_groups.return_value = [{"id": 30, "name": "ТЕСТ-101"}]
        self.repository.is_registered.return_value = False
        self.repository.get_session.return_value = None
        self.repository.authenticate_by_phone.return_value = None
        self.repository.list_academic_history.return_value = []
        self.repository.list_history.return_value = []
        self.repository.list_progress_courses.return_value = []
        self.repository.list_schedule.return_value = []
        self.repository.get_courses.return_value = []
        self.repository.list_synthetic_profiles.return_value = [
            {"id": 21, "name": "Карбышев Олег"},
            {"id": 22, "name": "Юрьева Злата"},
            {"id": 23, "name": "Тимур Гиззятов"},
        ]
        self.bot = MaxBot(
            "test-token",
            repository=self.repository,
            agent=Mock(),
            client=AsyncMock(),
        )
        self.bot.send_message = AsyncMock()
        self.bot.answer_callback = AsyncMock()

    @staticmethod
    def contact_attachment(phone: str = "79990000001", valid: bool = True) -> dict:
        vcf = f"BEGIN:VCARD\r\nVERSION:3.0\r\nTEL;TYPE=cell:{phone}\r\nFN:Test User\r\nEND:VCARD\r\n"
        signature = hmac.new(b"test-token", vcf.encode(), hashlib.sha256).hexdigest()
        return {
            "type": "contact",
            "payload": {"vcf_info": vcf, "hash": signature if valid else "invalid"},
        }

    async def test_start_requests_phone(self) -> None:
        await self.bot.handle_update(
            {"update_type": "bot_started", "chat_id": 123, "user": {"user_id": 77}}
        )
        self.repository.set_session.assert_called_once_with("77", WAIT_PHONE, {})
        body = self.bot.send_message.await_args.args[1]
        self.assertIn("телефона", body["text"])
        self.assertEqual(
            body["attachments"][0]["payload"]["buttons"][0][0]["type"],
            "request_contact",
        )

    async def test_registered_user_is_not_asked_for_phone_again(self) -> None:
        self.repository.is_registered.return_value = True
        await self.bot.request_phone("77", 123)
        self.repository.set_session.assert_called_once_with("77", "ready", {})
        body = self.bot.send_message.await_args.args[1]
        self.assertIn("С возвращением", body["text"])
        self.assertNotIn("request_contact", str(body))

    def test_contact_signature_and_phone_normalization(self) -> None:
        attachment = self.contact_attachment("8 (999) 000-00-01")
        self.assertEqual(verified_phone_from_contact(attachment, "test-token"), "+79990000001")
        self.assertEqual(normalize_phone("9990000001"), "+79990000001")
        with self.assertRaises(ValueError):
            verified_phone_from_contact(self.contact_attachment(valid=False), "test-token")

    def test_long_agent_answer_is_split_between_words(self) -> None:
        text = "A" * 3490 + " работа с репозиториями будет знакомой. " + "B" * 100
        chunks = split_message(text)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].endswith("работа с"))
        self.assertTrue(chunks[1].startswith("репозиториями"))

    def test_max_formatter_removes_unrendered_markdown(self) -> None:
        self.assertEqual(format_for_max("### **Заголовок**\n* пункт"), "📌 Заголовок\n— пункт")

    async def test_known_phone_opens_menu(self) -> None:
        self.repository.authenticate_by_phone.return_value = {
            "id": 5,
            "registration_completed_at": "2026-09-01",
        }
        await self.bot.handle_update(
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 77},
                    "recipient": {"chat_id": 123},
                    "body": {"attachments": [self.contact_attachment()]},
                },
            }
        )
        self.repository.authenticate_by_phone.assert_called_once_with("77", "+79990000001")
        self.repository.set_session.assert_called_once_with("77", "ready", {})
        self.assertIn("С возвращением", self.bot.send_message.await_args.args[1]["text"])

    async def test_new_phone_offers_registration_or_synthetic_profile(self) -> None:
        self.repository.get_session.return_value = {"state": WAIT_PHONE, "data": {}}
        await self.bot.handle_update(
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 77},
                    "recipient": {"chat_id": 123},
                    "body": {"attachments": [self.contact_attachment()]},
                },
            }
        )
        self.repository.set_session.assert_called_once_with(
            "77",
            WAIT_PROFILE_CHOICE,
            {"phone": "+79990000001", "_resume_state": WAIT_NAME},
        )
        body = self.bot.send_message.await_args.args[1]
        self.assertIn("Упс, такой студент не найден", body["text"])
        self.assertIn("профиль для демо", body["text"])
        button_texts = [row[0]["text"] for row in body["attachments"][0]["payload"]["buttons"]]
        self.assertIn("👤 Карбышев Олег", button_texts)

    async def test_self_registration_choice_starts_questionnaire(self) -> None:
        self.repository.get_session.return_value = {
            "state": WAIT_PROFILE_CHOICE,
            "data": {"phone": "+79990000001", "_resume_state": WAIT_NAME},
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "self", "payload": "auth:self"}}, "77"
        )
        self.repository.set_session.assert_called_once_with(
            "77", WAIT_NAME, {"phone": "+79990000001"}
        )
        self.assertIn("ФИО", self.bot.answer_callback.await_args.args[1]["text"])
        self.assertNotIn("Упс, такой студент не найден", self.bot.answer_callback.await_args.args[1]["text"])

    async def test_synthetic_profile_choice_activates_copy(self) -> None:
        self.repository.get_session.return_value = {
            "state": WAIT_PROFILE_CHOICE,
            "data": {"phone": "+79995554433", "_resume_state": WAIT_NAME},
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "synthetic", "payload": "auth:synthetic:21"}},
            "77",
        )
        self.repository.activate_synthetic_profile.assert_called_once_with(
            "77", "+79995554433", 21
        )
        self.repository.set_session.assert_called_once_with("77", "ready", {})
        self.assertIn("Профиль найден. Добро пожаловать", self.bot.answer_callback.await_args.args[1]["text"])

    async def test_profile_reset_requires_phone_confirmation(self) -> None:
        await self.bot.handle_callback(
            {"callback": {"callback_id": "reset", "payload": "reset:confirm"}}, "77"
        )
        self.repository.reset_registration.assert_called_once_with("77")
        body = self.bot.answer_callback.await_args.args[1]
        self.assertIn("подтверди номер", body["text"])
        self.assertEqual(
            body["attachments"][0]["payload"]["buttons"][0][0]["type"],
            "request_contact",
        )

    async def test_phone_conflict_fails_closed(self) -> None:
        self.repository.authenticate_by_phone.side_effect = ValueError("conflict")
        await self.bot.handle_contact("77", 123, self.contact_attachment())
        self.assertIn("Не удалось подтвердить", self.bot.send_message.await_args.args[1]["text"])

    async def test_name_advances_to_university(self) -> None:
        self.repository.get_session.return_value = {"state": WAIT_NAME, "data": {}}
        await self.bot.handle_update(
            {
                "update_type": "message_created",
                "message": {
                    "sender": {"user_id": 77},
                    "recipient": {"chat_id": 123},
                    "body": {"text": "Иван Иванов"},
                },
            }
        )
        self.repository.update_session_data.assert_called_once_with(
            "77", "wait_university", name="Иван Иванов"
        )

    async def test_registration_callbacks(self) -> None:
        self.repository.get_session.return_value = {
            "state": "wait_university",
            "data": {"phone": "+79990000001"},
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb1", "payload": "reg:university:1"}}, "77"
        )
        self.repository.update_session_data.assert_called_with(
            "77", WAIT_FACULTY, university_id=1
        )
        self.repository.get_session.return_value = {
            "state": WAIT_FACULTY,
            "data": {"phone": "+79990000001", "university_id": 1},
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb2", "payload": "reg:faculty:10"}}, "77"
        )
        self.repository.update_session_data.assert_called_with("77", WAIT_SPECIALTY, faculty_id=10)
        self.repository.get_session.return_value = {
            "state": WAIT_SPECIALTY,
            "data": {
                "phone": "+79990000001",
                "university_id": 1,
                "faculty_id": 10,
            },
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb3", "payload": "reg:specialty:20"}}, "77"
        )
        self.repository.update_session_data.assert_called_with("77", WAIT_GROUP, specialty_id=20)
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb4", "payload": "reg:group:30"}}, "77"
        )
        self.repository.update_session_data.assert_called_with("77", WAIT_YEAR, group_id=30)
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb5", "payload": "reg:year:3"}}, "77"
        )
        self.repository.update_session_data.assert_called_with("77", WAIT_GOAL, study_year=3)

    async def test_university_without_faculties_skips_empty_faculty_screen(self) -> None:
        self.repository.get_session.return_value = {
            "state": WAIT_UNIVERSITY,
            "data": {"phone": "+79990000001"},
        }
        self.repository.list_faculties.return_value = []
        await self.bot.handle_callback(
            {"callback": {"callback_id": "university", "payload": "reg:university:1"}}, "77"
        )
        self.repository.update_session_data.assert_called_once_with(
            "77", WAIT_YEAR, university_id=1, faculty_id=None, specialty_id=None, group_id=None
        )
        self.assertIn("нет списка факультетов", self.bot.answer_callback.await_args.args[1]["text"])

    async def test_experience_completes_registration_without_conditions(self) -> None:
        handled = await self.bot.handle_registration_text(
            "77", 123, "wait_experience", "Python и SQL"
        )
        self.assertTrue(handled)
        self.repository.update_session_data.assert_called_once_with(
            "77", "wait_experience", experience="Python и SQL"
        )
        self.repository.complete_registration.assert_called_once_with("77")

    async def test_other_university_is_entered_as_text(self) -> None:
        self.repository.get_session.return_value = {
            "state": WAIT_UNIVERSITY,
            "data": {"phone": "+79990000001"},
        }
        await self.bot.handle_callback(
            {"callback": {"callback_id": "other-university", "payload": "reg:university:none"}},
            "77",
        )
        self.repository.update_session_data.assert_called_once_with(
            "77",
            WAIT_CUSTOM_UNIVERSITY,
            university_id=None,
            faculty_id=None,
            specialty_id=None,
            group_id=None,
        )
        self.assertIn("название своего университета", self.bot.answer_callback.await_args.args[1]["text"])

        self.repository.reset_mock()
        await self.bot.handle_registration_text(
            "77", 123, WAIT_CUSTOM_UNIVERSITY, "Казанский федеральный университет"
        )
        self.repository.update_session_data.assert_called_once_with(
            "77",
            "wait_custom_faculty",
            custom_university_name="Казанский федеральный университет",
        )

    def test_history_contains_academic_and_course_blocks(self) -> None:
        self.repository.list_academic_history.return_value = [
            {
                "name": "Базы данных",
                "start_year": 2025,
                "end_year": 2026,
                "polugodie": 2,
                "semester_number": 6,
                "grade": "5",
            }
        ]
        self.repository.list_history.return_value = [
            {
                "name": "Внутренние базы данных",
                "status": "selected",
                "source": "university",
                "progress_percent": 0,
                "latest_stage_type": "planned",
            },
            {
                "name": "SQL на Stepik",
                "status": "completed",
                "source": "stepik",
                "progress_percent": 100,
                "latest_stage_type": "completed",
            },
        ]
        text = self.bot.history_body("77")["text"]
        self.assertNotIn("УЧЕБНЫЙ ГОД", text)
        self.assertIn("   6 СЕМЕСТР", text)
        self.assertIn("       Базы данных — 5", text)
        self.assertIn("🏛 УНИВЕРСИТЕТСКИЕ КУРСЫ", text)
        self.assertIn("🧩 ДОПОЛНИТЕЛЬНЫЕ КУРСЫ", text)
        self.assertIn("   🔖 SQL на Stepik\n       🏁 Завершён · Прогресс: 100%", text)

    async def test_profile_contains_faculty_specialty_and_group(self) -> None:
        self.repository.get_user.return_value = {
            "name": "Елена Кузнецова",
            "phone": "+79021283652",
            "university_name": "Тестовый университет",
            "faculty_name": "Факультет информационных технологий",
            "specialty_name": "Программная инженерия",
            "group_name": "ТЕСТ-101",
            "study_year": 2,
            "goal": "Стать системным аналитиком",
            "experience": "Основы Java и UML",
        }
        text = (await self.bot.profile_body("200352189"))["text"]
        self.assertIn("Факультет: Факультет информационных технологий", text)
        self.assertIn("Специальность: Программная инженерия", text)
        self.assertIn("Группа: ТЕСТ-101", text)

    def test_schedule_is_formatted_for_current_period(self) -> None:
        self.repository.list_schedule.return_value = [
            {
                "day_of_week": 1,
                "start_time": time(9, 0),
                "end_time": time(10, 30),
                "lesson_type": "lecture",
                "subject_name": "Базы данных",
                "teacher_name": "Иван Иванович",
                "building_name": "Корпус A",
                "room_number": "301",
            }
        ]
        text = self.bot.schedule_body("77", datetime(2026, 9, 23))["text"]
        self.repository.list_schedule.assert_called_once_with("77", 2026, 1)
        self.assertIn("Понедельник", text)
        self.assertIn("09:00–10:30  Базы данных", text)
        self.assertIn("Лекция · Иван Иванович", text)

    async def test_add_to_plan_button(self) -> None:
        self.repository.is_registered.return_value = True
        await self.bot.handle_callback(
            {"callback": {"callback_id": "cb3", "payload": "plan:add:42"}}, "77"
        )
        self.repository.set_course_status.assert_called_once_with("77", 42, "selected")

    async def test_course_progress_is_recorded(self) -> None:
        self.repository.is_registered.return_value = True
        await self.bot.handle_callback(
            {"callback": {"callback_id": "progress", "payload": "progress:set:42:50"}},
            "77",
        )
        self.repository.record_course_progress.assert_called_once_with(
            "77", 42, progress_percent=50
        )

    async def test_progress_menu_contains_only_planned_courses(self) -> None:
        self.repository.is_registered.return_value = True
        self.repository.list_progress_courses.return_value = [
            {
                "course_id": 42,
                "name": "SQL для аналитики",
                "source": "stepik",
                "status": "in_progress",
                "progress_percent": 25,
            }
        ]
        await self.bot.handle_callback(
            {"callback": {"callback_id": "progress", "payload": "history:progress"}},
            "77",
        )
        body = self.bot.answer_callback.await_args.args[1]
        self.assertIn("Выбери курс", body["text"])
        self.assertIn("25% · SQL для аналитики", str(body["attachments"]))

    async def test_course_can_be_removed_from_plan_after_confirmation(self) -> None:
        self.repository.is_registered.return_value = True
        self.repository.list_progress_courses.return_value = [
            {"course_id": 42, "name": "SQL для аналитики", "status": "selected", "progress_percent": 0}
        ]
        await self.bot.handle_callback(
            {"callback": {"callback_id": "remove", "payload": "history:remove"}}, "77"
        )
        self.assertIn("Выбери курс", self.bot.answer_callback.await_args.args[1]["text"])
        await self.bot.handle_callback(
            {"callback": {"callback_id": "confirm", "payload": "history:remove:confirm:42"}}, "77"
        )
        self.repository.remove_course_from_plan.assert_called_once_with("77", 42)

    async def test_profile_goal_and_experience_can_be_edited(self) -> None:
        self.repository.is_registered.return_value = True
        await self.bot.handle_callback(
            {"callback": {"callback_id": "goal", "payload": "profile:edit_goal"}}, "77"
        )
        self.repository.set_session.assert_called_once_with("77", WAIT_EDIT_GOAL, {})
        self.repository.reset_mock()
        self.repository.is_registered.return_value = True
        self.repository.get_session.return_value = {"state": WAIT_EDIT_GOAL, "data": {}}
        await self.bot.handle_text(
            {"message": {"body": {"text": "Стать DevOps-инженером"}}}, "77", 123
        )
        self.repository.update_profile_field.assert_called_once_with("77", "goal", "Стать DevOps-инженером")
        self.repository.set_session.assert_called_once_with("77", "ready", {})
        self.repository.reset_mock()
        self.repository.is_registered.return_value = True
        await self.bot.handle_callback(
            {"callback": {"callback_id": "experience", "payload": "profile:edit_experience"}}, "77"
        )
        self.repository.set_session.assert_called_once_with("77", WAIT_EDIT_EXPERIENCE, {})

    async def test_recommendation_context_is_passed_to_followup(self) -> None:
        context = {
            "recommended_course_ids": [42],
            "recommendation_question": "Что пройти по SQL?",
            "recommendation_answer": "Рекомендую курс SQL.",
        }
        self.repository.get_session.return_value = {
            "state": "ready",
            "data": {"recommendation_context": context},
        }
        self.bot.agent.ask_with_metadata.return_value = AgentResponse(
            answer="Он соответствует твоей цели.",
            route="recommendation_explanation",
            course_ids=[42],
        )
        await self.bot.handle_agent_question("77", 123, "Почему именно этот?")
        self.bot.agent.ask_with_metadata.assert_called_once_with(
            "77", "Почему именно этот?", context
        )

    async def test_new_recommendation_is_saved_as_conversation_context(self) -> None:
        self.repository.get_session.return_value = {"state": "ready", "data": {}}
        self.bot.agent.ask_with_metadata.return_value = AgentResponse(
            answer="Рекомендую SQL для начинающих.",
            route="topic_recommendation",
            course_ids=[42],
        )
        await self.bot.handle_agent_question("77", 123, "Что пройти по SQL?")
        self.repository.set_session.assert_called_once_with(
            "77",
            "ready",
            {
                "recommendation_context": {
                    "recommended_course_ids": [42],
                    "recommendation_question": "Что пройти по SQL?",
                    "recommendation_answer": "Рекомендую SQL для начинающих.",
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
