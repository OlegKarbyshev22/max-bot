import asyncio
import base64
import hashlib
import hmac
import logging
import os
import re
import ssl
from datetime import datetime
from pathlib import Path
from typing import Any

import certifi
import httpx
from dotenv import load_dotenv

from agent.src.agent import CourseAgent
from app.db import BotRepository


API_URL = "https://platform-api2.max.ru"
POLL_TIMEOUT = 30
PROJECT_DIR = Path(__file__).resolve().parent
MINISTRY_CERTIFICATES = (
    PROJECT_DIR / "certs" / "russian_trusted_root_ca.cer",
    PROJECT_DIR / "certs" / "russian_trusted_sub_ca.cer",
)

WAIT_PHONE = "wait_phone"
WAIT_PROFILE_CHOICE = "wait_profile_choice"
WAIT_NAME = "wait_name"
WAIT_UNIVERSITY = "wait_university"
WAIT_FACULTY = "wait_faculty"
WAIT_SPECIALTY = "wait_specialty"
WAIT_GROUP = "wait_group"
WAIT_YEAR = "wait_year"
WAIT_GOAL = "wait_goal"
WAIT_EXPERIENCE = "wait_experience"
WAIT_HISTORY_QUERY = "wait_history_query"
WAIT_EDIT_GOAL = "wait_edit_goal"
WAIT_EDIT_EXPERIENCE = "wait_edit_experience"
WAIT_CUSTOM_UNIVERSITY = "wait_custom_university"
WAIT_CUSTOM_FACULTY = "wait_custom_faculty"
WAIT_CUSTOM_SPECIALTY = "wait_custom_specialty"
READY = "ready"

REGISTRATION_STATES = {
    WAIT_NAME,
    WAIT_UNIVERSITY,
    WAIT_FACULTY,
    WAIT_SPECIALTY,
    WAIT_GROUP,
    WAIT_YEAR,
    WAIT_GOAL,
    WAIT_EXPERIENCE,
    WAIT_CUSTOM_UNIVERSITY,
    WAIT_CUSTOM_FACULTY,
    WAIT_CUSTOM_SPECIALTY,
}


def keyboard(buttons: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"type": "inline_keyboard", "payload": {"buttons": buttons}}


def callback_button(text: str, payload: str) -> dict[str, str]:
    return {"type": "callback", "text": text, "payload": payload}


def request_contact_button(text: str) -> dict[str, str]:
    return {"type": "request_contact", "text": text}


def main_menu(prefix: str | None = None) -> dict[str, Any]:
    text = "Что хочешь сделать?"
    if prefix:
        text = f"{prefix}\n\n{text}"
    return {
        "text": text,
        "attachments": [
            keyboard(
                [
                    [
                        callback_button("👤 Мой профиль", "menu:profile"),
                        callback_button("🎯 Подобрать курс", "menu:recommend"),
                    ],
                    [
                        callback_button("📚 История обучения", "menu:history"),
                        callback_button("🗓 Расписание", "menu:schedule"),
                    ],
                    [
                        callback_button("✏️ Изменить профиль", "menu:reset"),
                    ],
                ]
            )
        ],
    }


def back_button() -> dict[str, Any]:
    return keyboard([[callback_button("⬅️ В меню", "menu:home")]])


def text_message(text: str, attachment: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"text": text}
    if attachment:
        body["attachments"] = [attachment]
    return body


def split_message(text: str, max_length: int = 3500) -> list[str]:
    """Split a long answer without breaking a word or a Markdown paragraph."""
    if not text:
        return ["Нет ответа."]
    chunks: list[str] = []
    remainder = text.strip()
    while len(remainder) > max_length:
        window = remainder[: max_length + 1]
        paragraph = window.rfind("\n\n")
        line = window.rfind("\n")
        sentence = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
        word = window.rfind(" ")
        if paragraph > 0:
            split_at = paragraph
        elif line > 0:
            split_at = line
        elif sentence > 0:
            split_at = sentence + 1
        elif word > 0:
            split_at = word
        else:
            split_at = max_length
        chunks.append(remainder[:split_at].rstrip())
        remainder = remainder[split_at:].lstrip()
    if remainder:
        chunks.append(remainder)
    return chunks


def format_for_max(text: str) -> str:
    """MAX text messages do not render Markdown, so use broadly supported text."""
    text = text.replace("\r\n", "\n").replace("**", "").replace("__", "")
    text = re.sub(r"^\s*#{1,6}\s*", "📌 ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*•]\s+", "— ", text, flags=re.MULTILINE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def contact_prompt() -> dict[str, Any]:
    return text_message(
        "Подтверди номер телефона, чтобы войти или зарегистрироваться.",
        keyboard([[request_contact_button("📱 Поделиться телефоном")]]),
    )


def normalize_phone(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if not 10 <= len(digits) <= 15:
        raise ValueError("Phone number must contain between 10 and 15 digits")
    return "+" + digits


def verified_phone_from_contact(attachment: dict[str, Any], token: str) -> str:
    if attachment.get("type") != "contact":
        raise ValueError("Not a contact attachment")
    payload = attachment.get("payload") or {}
    vcf_info = payload.get("vcf_info")
    supplied_hash = payload.get("hash")
    if not isinstance(vcf_info, str) or not isinstance(supplied_hash, str):
        raise ValueError("Contact does not contain a signed VCard")
    normalized_vcf = vcf_info.replace("\\r\\n", "\r\n").replace("\\n", "\n")
    digest = hmac.new(token.encode("utf-8"), normalized_vcf.encode("utf-8"), hashlib.sha256).digest()
    expected_hashes = (
        digest.hex(),
        base64.b64encode(digest).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii").rstrip("="),
    )
    if not any(hmac.compare_digest(supplied_hash, expected) for expected in expected_hashes):
        raise ValueError("Contact signature is invalid")
    phone_match = re.search(r"^TEL[^:]*:(.+)$", normalized_vcf, flags=re.IGNORECASE | re.MULTILINE)
    if not phone_match:
        raise ValueError("VCard does not contain a phone")
    return normalize_phone(phone_match.group(1).strip())


def create_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    for certificate_path in MINISTRY_CERTIFICATES:
        context.load_verify_locations(cafile=certificate_path)
    return context


class MaxBot:
    def __init__(
        self,
        token: str,
        repository: BotRepository | None = None,
        agent: CourseAgent | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.token = token
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=API_URL,
            headers={"Authorization": token},
            timeout=httpx.Timeout(POLL_TIMEOUT + 15),
            verify=create_ssl_context(),
        )
        self.repository = repository or BotRepository()
        self.agent = agent or CourseAgent()
        self.marker: int | None = None
        self.user_locks: dict[str, asyncio.Lock] = {}
        self.agent_semaphore = asyncio.Semaphore(1)
        self.tasks: set[asyncio.Task] = set()

    async def close(self) -> None:
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        if self._owns_client:
            await self.client.aclose()

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_me(self) -> dict[str, Any]:
        return await self.request("GET", "/me")

    async def get_updates(self) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": POLL_TIMEOUT,
            "limit": 100,
            "types": "bot_started,message_created,message_callback",
        }
        if self.marker is not None:
            params["marker"] = self.marker
        data = await self.request("GET", "/updates", params=params)
        self.marker = data.get("marker", self.marker)
        return data.get("updates", [])

    async def send_message(self, chat_id: int, body: dict[str, Any]) -> None:
        await self.request("POST", "/messages", params={"chat_id": chat_id}, json=body)

    async def answer_callback(self, callback_id: str, body: dict[str, Any]) -> None:
        await self.request(
            "POST", "/answers", params={"callback_id": callback_id}, json={"message": body}
        )

    @staticmethod
    def update_identity(update: dict[str, Any]) -> tuple[str | None, int | None]:
        update_type = update.get("update_type")
        if update_type == "message_callback":
            user_id = (update.get("callback") or {}).get("user", {}).get("user_id")
            message = update.get("message") or {}
            chat_id = (message.get("recipient") or {}).get("chat_id")
        elif update_type == "message_created":
            message = update.get("message") or {}
            user_id = (message.get("sender") or {}).get("user_id")
            recipient = message.get("recipient") or {}
            chat_id = recipient.get("chat_id") or update.get("chat_id")
        else:
            user_id = (update.get("user") or {}).get("user_id")
            chat_id = update.get("chat_id")
        return (str(user_id) if user_id is not None else None, int(chat_id) if chat_id else None)

    def university_prompt(self) -> dict[str, Any]:
        rows = [
            [callback_button(item["name"][:40], f"reg:university:{item['id']}")]
            for item in self.repository.list_universities()
        ]
        rows.append([callback_button("Другой", "reg:university:none")])
        return text_message("Выбери свой университет:", keyboard(rows))

    def faculty_prompt(self, university_id: int) -> dict[str, Any]:
        rows = [
            [callback_button(item["name"][:50], f"reg:faculty:{item['id']}")]
            for item in self.repository.list_faculties(university_id)
        ]
        rows.append([callback_button("Не указано", "reg:faculty:none")])
        return text_message("Выбери факультет:", keyboard(rows))

    def specialty_prompt(self, university_id: int, faculty_id: int) -> dict[str, Any]:
        rows = [
            [callback_button(item["name"][:50], f"reg:specialty:{item['id']}")]
            for item in self.repository.list_specialties(university_id, faculty_id)
        ]
        rows.append([callback_button("Не указано", "reg:specialty:none")])
        return text_message("Выбери специальность:", keyboard(rows))

    def group_prompt(
        self, university_id: int, faculty_id: int, specialty_id: int
    ) -> dict[str, Any]:
        rows = [
            [callback_button(item["name"][:50], f"reg:group:{item['id']}")]
            for item in self.repository.list_student_groups(
                university_id, faculty_id, specialty_id
            )
        ]
        rows.append([callback_button("Не указана", "reg:group:none")])
        return text_message("Выбери учебную группу:", keyboard(rows))

    def synthetic_profile_prompt(self, intro: str | None = None) -> dict[str, Any]:
        rows = [
            [callback_button("✍️ Зарегистрироваться самостоятельно", "auth:self")]
        ]
        rows.extend(
            [callback_button(f"👤 {item['name']}", f"auth:synthetic:{item['id']}")]
            for item in self.repository.list_synthetic_profiles()
        )
        return text_message(
            intro or "Выбери профиль для демо или заполни анкету самостоятельно.",
            keyboard(rows),
        )

    @staticmethod
    def year_prompt() -> dict[str, Any]:
        rows = [
            [callback_button(f"{year} курс", f"reg:year:{year}") for year in range(1, 4)],
            [callback_button(f"{year} курс", f"reg:year:{year}") for year in range(4, 7)],
        ]
        return text_message("На каком курсе ты учишься?", keyboard(rows))

    def registration_prompt(self, state: str) -> dict[str, Any]:
        prompts = {
            WAIT_PHONE: "Подтверди номер телефона, чтобы продолжить.",
            WAIT_PROFILE_CHOICE: "Выбери способ создания профиля.",
            WAIT_NAME: "👋 Привет! Я помогу подобрать образовательную траекторию.\n\nНапиши свои ФИО одним сообщением.",
            WAIT_GOAL: "Расскажи, чему хочешь научиться и какая у тебя профессиональная цель.",
            WAIT_EXPERIENCE: "Опиши свой опыт: технологии, предметы и уже пройденные курсы.",
            WAIT_CUSTOM_UNIVERSITY: "Напиши название своего университета.",
            WAIT_CUSTOM_FACULTY: "Напиши название своего факультета.",
            WAIT_CUSTOM_SPECIALTY: "Напиши название своей специальности или направления подготовки.",
        }
        if state == WAIT_PHONE:
            return contact_prompt()
        if state == WAIT_PROFILE_CHOICE:
            return self.synthetic_profile_prompt()
        if state == WAIT_UNIVERSITY:
            return self.university_prompt()
        if state == WAIT_YEAR:
            return self.year_prompt()
        return text_message(prompts.get(state, "Продолжим регистрацию."))

    async def request_phone(self, user_id: str, chat_id: int) -> None:
        if self.repository.is_registered(user_id):
            self.repository.set_session(user_id, READY, {})
            await self.send_message(chat_id, main_menu("С возвращением!"))
            return
        session = self.repository.get_session(user_id)
        if not session:
            self.repository.set_session(user_id, WAIT_PHONE, {})
        elif session.get("state") != WAIT_PHONE:
            data = dict(session.get("data") or {})
            if session.get("state") in REGISTRATION_STATES:
                data["_resume_state"] = session["state"]
            self.repository.set_session(user_id, WAIT_PHONE, data)
        await self.send_message(chat_id, contact_prompt())

    async def handle_contact(
        self, user_id: str, chat_id: int, attachment: dict[str, Any]
    ) -> None:
        try:
            phone = verified_phone_from_contact(attachment, self.token)
            user = self.repository.authenticate_by_phone(user_id, phone)
        except ValueError as error:
            logging.warning("Contact authentication rejected for user %s: %s", user_id, error)
            await self.send_message(
                chat_id,
                text_message("Не удалось подтвердить телефон. Используй кнопку ниже.", contact_prompt()["attachments"][0]),
            )
            return

        if user and user.get("registration_completed_at"):
            self.repository.set_session(user_id, READY, {})
            await self.send_message(chat_id, main_menu("✅ Номер подтверждён. С возвращением!"))
            return

        session = self.repository.get_session(user_id) or {"state": WAIT_PHONE, "data": {}}
        data = dict(session.get("data") or {})
        previous_phone = data.get("phone")
        if previous_phone and previous_phone != phone:
            data = {}
        resume_state = data.get("_resume_state", WAIT_NAME)
        if resume_state not in REGISTRATION_STATES:
            resume_state = WAIT_NAME
        data["phone"] = phone
        data["_resume_state"] = resume_state
        self.repository.set_session(user_id, WAIT_PROFILE_CHOICE, data)
        await self.send_message(
            chat_id,
            self.synthetic_profile_prompt(
                "Упс, такой студент не найден.\n\n"
                "Введите данные самостоятельно или выберите профиль для демо."
            ),
        )

    async def handle_registration_text(
        self, user_id: str, chat_id: int, state: str, text: str
    ) -> bool:
        if state == WAIT_PROFILE_CHOICE:
            await self.send_message(chat_id, self.synthetic_profile_prompt())
            return True
        if state == WAIT_NAME:
            if len(text) < 3:
                await self.send_message(chat_id, text_message("Укажи имя длиной не менее трёх символов."))
                return True
            self.repository.update_session_data(user_id, WAIT_UNIVERSITY, name=text[:200])
            await self.send_message(chat_id, self.university_prompt())
            return True
        if state == WAIT_UNIVERSITY:
            await self.send_message(chat_id, self.university_prompt())
            return True
        session_data = dict((self.repository.get_session(user_id) or {}).get("data") or {})
        if state == WAIT_FACULTY:
            university_id = session_data.get("university_id")
            if university_id:
                await self.send_message(chat_id, self.faculty_prompt(university_id))
            else:
                self.repository.update_session_data(user_id, WAIT_YEAR)
                await self.send_message(chat_id, self.year_prompt())
            return True
        if state == WAIT_SPECIALTY:
            university_id = session_data.get("university_id")
            faculty_id = session_data.get("faculty_id")
            if university_id and faculty_id:
                await self.send_message(
                    chat_id, self.specialty_prompt(university_id, faculty_id)
                )
            else:
                self.repository.update_session_data(user_id, WAIT_YEAR)
                await self.send_message(chat_id, self.year_prompt())
            return True
        if state == WAIT_GROUP:
            university_id = session_data.get("university_id")
            faculty_id = session_data.get("faculty_id")
            specialty_id = session_data.get("specialty_id")
            if university_id and faculty_id and specialty_id:
                await self.send_message(
                    chat_id,
                    self.group_prompt(university_id, faculty_id, specialty_id),
                )
            else:
                self.repository.update_session_data(user_id, WAIT_YEAR)
                await self.send_message(chat_id, self.year_prompt())
            return True
        if state == WAIT_YEAR:
            await self.send_message(chat_id, self.year_prompt())
            return True
        if state == WAIT_GOAL:
            self.repository.update_session_data(user_id, WAIT_EXPERIENCE, goal=text[:2000])
            await self.send_message(chat_id, self.registration_prompt(WAIT_EXPERIENCE))
            return True
        if state == WAIT_EXPERIENCE:
            self.repository.update_session_data(user_id, WAIT_EXPERIENCE, experience=text[:4000])
            self.repository.complete_registration(user_id)
            await self.send_message(chat_id, main_menu("✅ Готово! Профиль сохранён."))
            return True
        if state == WAIT_CUSTOM_UNIVERSITY:
            self.repository.update_session_data(
                user_id, WAIT_CUSTOM_FACULTY, custom_university_name=text[:300]
            )
            await self.send_message(chat_id, self.registration_prompt(WAIT_CUSTOM_FACULTY))
            return True
        if state == WAIT_CUSTOM_FACULTY:
            self.repository.update_session_data(user_id, WAIT_CUSTOM_SPECIALTY, custom_faculty_name=text[:300])
            await self.send_message(chat_id, self.registration_prompt(WAIT_CUSTOM_SPECIALTY))
            return True
        if state == WAIT_CUSTOM_SPECIALTY:
            self.repository.update_session_data(user_id, WAIT_YEAR, custom_specialty_name=text[:300])
            await self.send_message(chat_id, self.year_prompt())
            return True
        return False

    async def profile_body(self, user_id: str) -> dict[str, Any]:
        user = self.repository.get_user(user_id)
        if not user:
            return text_message("Профиль не найден.", back_button())
        university = user.get("custom_university_name") or user.get("university_name") or "не указан"
        faculty = user.get("custom_faculty_name") or user.get("faculty_name") or "не указан"
        specialty = user.get("custom_specialty_name") or user.get("specialty_name") or "не указана"
        student_group = user.get("group_name") or "не указана"
        phone = user.get("phone") or "не указан"
        masked_phone = phone if len(phone) < 7 else f"{phone[:4]}***{phone[-4:]}"
        return text_message(
            "👤 МОЙ ПРОФИЛЬ\n"
            "Данные и учебная траектория\n\n"
            f"{user['name']}\n"
            f"Телефон: {masked_phone}\n\n"
            "🎓 ОБУЧЕНИЕ\n"
            f"Университет: {university}\n"
            f"Факультет: {faculty}\n"
            f"Специальность: {specialty}\n"
            f"Группа: {student_group}\n"
            f"Курс: {user.get('study_year') or 'не указан'}\n\n"
            "🎯 ЦЕЛЬ\n"
            f"{user.get('goal') or 'не указана'}\n\n"
            "🧠 ОПЫТ\n"
            f"{user.get('experience') or 'не указан'}",
            keyboard([
                [callback_button("🎯 Изменить цель", "profile:edit_goal")],
                [callback_button("🧠 Изменить опыт", "profile:edit_experience")],
                [callback_button("⬅️ В меню", "menu:home")],
            ]),
        )

    def history_body(self, user_id: str) -> dict[str, Any]:
        academic_items = self.repository.list_academic_history(user_id)
        course_items = self.repository.list_history(user_id)
        status_names = {
            "completed": "🏁 Завершён",
            "in_progress": "🚀 В процессе",
            "selected": "🧭 В плане",
        }
        lines = ["📋 ИСТОРИЯ ОБУЧЕНИЯ", "", "🎓 УСПЕВАЕМОСТЬ"]
        if academic_items:
            semesters: dict[int, list[dict[str, Any]]] = {}
            for item in academic_items[:30]:
                semester_number = item.get("semester_number") or item["polugodie"]
                semesters.setdefault(semester_number, []).append(item)
            for semester in sorted(semesters):
                lines.append(f"   {semester} СЕМЕСТР")
                for item in semesters[semester]:
                    lines.append(f"       {item['name']} — {item['grade']}")
            lines.append("")
        else:
            lines.append("Пока нет оценок за учебные периоды")

        def append_course_section(title: str, items: list[dict[str, Any]]) -> None:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(title)
            if not items:
                lines.append("Пока нет добавленных курсов")
                return
            for item in items:
                status = (
                    "⏸️ На паузе"
                    if item.get("latest_stage_type") == "paused"
                    else status_names.get(item["status"], item["status"])
                )
                progress = item.get("progress_percent") or 0
                lines.extend([
                    f"   🔖 {item['name']}",
                    f"       {status} · Прогресс: {progress}%",
                    "",
                ])

        university_courses = [item for item in course_items[:30] if item["source"] == "university"]
        additional_courses = [item for item in course_items[:30] if item["source"] != "university"]
        append_course_section("🏛 УНИВЕРСИТЕТСКИЕ КУРСЫ", university_courses)
        append_course_section("🧩 ДОПОЛНИТЕЛЬНЫЕ КУРСЫ", additional_courses)

        buttons = [
            [callback_button("➕ Добавить курс", "history:add")],
            [callback_button("📈 Обновить прогресс", "history:progress")],
            [callback_button("🗑 Удалить из плана", "history:remove")],
            [callback_button("⬅️ В меню", "menu:home")],
        ]
        return text_message("\n".join(lines), keyboard(buttons))

    def schedule_body(self, user_id: str, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now()
        academic_start_year = current.year if current.month >= 9 else current.year - 1
        polugodie = 1 if current.month >= 9 or current.month == 1 else 2
        items = self.repository.list_schedule(user_id, academic_start_year, polugodie)
        day_names = {
            1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг",
            5: "Пятница", 6: "Суббота", 7: "Воскресенье",
        }
        type_names = {
            "lecture": "лекция", "practice": "практика", "lab": "лабораторная",
            "seminar": "семинар",
        }
        lines = [
            "🗓 РАСПИСАНИЕ",
            f"{academic_start_year}/{academic_start_year + 1} · {polugodie} полугодие",
        ]
        if not items:
            lines.append("\nДля твоей группы занятий пока нет")
        else:
            previous_day = None
            for item in items:
                if item["day_of_week"] != previous_day:
                    lines.extend(["", f"📅 {day_names[item['day_of_week']]}"])
                    previous_day = item["day_of_week"]
                start = item["start_time"].strftime("%H:%M")
                end = item["end_time"].strftime("%H:%M")
                lines.append(
                    f"{start}–{end}  {item['subject_name']}\n"
                    f"{type_names[item['lesson_type']].capitalize()} · "
                    f"{item['teacher_name']} · {item['building_name']}, ауд. {item['room_number']}"
                )
        return text_message("\n".join(lines), back_button())

    async def handle_agent_question(self, user_id: str, chat_id: int, question: str) -> None:
        await self.send_message(chat_id, text_message("⏳ Анализирую запрос и каталог курсов…"))
        self.repository.log_message(user_id, "user", question)
        try:
            session = self.repository.get_session(user_id) or {}
            session_data = dict(session.get("data") or {})
            recommendation_context = session_data.get("recommendation_context")
            async with self.agent_semaphore:
                result = await asyncio.to_thread(
                    self.agent.ask_with_metadata,
                    user_id,
                    question,
                    recommendation_context,
                )
            recommendation_answer = format_for_max(result.answer)
            route_name = getattr(result.route, "value", result.route)
            if result.course_ids and route_name in {"topic_recommendation", "next_step"}:
                session_data["recommendation_context"] = {
                    "recommended_course_ids": result.course_ids,
                    "recommendation_question": question,
                    "recommendation_answer": recommendation_answer,
                }
                self.repository.set_session(user_id, READY, session_data)
                answer = (
                    f"{recommendation_answer}\n\n"
                    "💡 Хочешь узнать, почему я выбрал именно эти курсы? "
                    "Напиши: «Почему ты подобрал именно эти курсы?»"
                )
            else:
                answer = recommendation_answer
            self.repository.log_message(user_id, "assistant", answer, result.route, result.course_ids)
            course_buttons = []
            for course in self.repository.get_courses(result.course_ids)[:5]:
                title = course["name"][:42]
                course_buttons.append(
                    [callback_button(f"📌 {title}", f"plan:add:{course['id']}")]
                )
            course_buttons.append([callback_button("⬅️ В меню", "menu:home")])
            chunks = split_message(answer)
            for index, chunk in enumerate(chunks):
                attachment = keyboard(course_buttons) if index == len(chunks) - 1 else None
                await self.send_message(chat_id, text_message(chunk, attachment))
                if index < len(chunks) - 1:
                    await asyncio.sleep(0.55)
        except Exception:
            logging.exception("Agent request failed for user %s", user_id)
            await self.send_message(
                chat_id,
                text_message("Не удалось получить рекомендацию. Проверь работу LLM и базы данных и попробуй ещё раз.", back_button()),
            )

    async def handle_text(self, update: dict[str, Any], user_id: str, chat_id: int) -> None:
        message = update.get("message") or {}
        body = message.get("body") or {}
        attachments = body.get("attachments") or []
        contact = next((item for item in attachments if item.get("type") == "contact"), None)
        if contact:
            await self.handle_contact(user_id, chat_id, contact)
            return
        text = (body.get("text") or "").strip()
        if not text:
            await self.send_message(chat_id, text_message("Отправь текстовое сообщение."))
            return
        command = text.lower()
        if command in {"/start", "start", "старт"}:
            await self.request_phone(user_id, chat_id)
            return
        if command in {"/reset", "сброс"}:
            body = text_message(
                "Перезапустить регистрацию? Текущий профиль будет заменён после заполнения.",
                keyboard(
                    [[callback_button("Да, начать заново", "reset:confirm")], [callback_button("Отмена", "menu:home")]]
                ),
            )
            await self.send_message(chat_id, body)
            return

        session = self.repository.get_session(user_id)
        state = session["state"] if session else None
        if not self.repository.is_registered(user_id):
            if state is None or state == WAIT_PHONE:
                await self.request_phone(user_id, chat_id)
            else:
                await self.handle_registration_text(user_id, chat_id, state, text)
            return
        if state in {WAIT_CUSTOM_FACULTY, WAIT_CUSTOM_SPECIALTY}:
            await self.handle_registration_text(user_id, chat_id, state, text)
            return
        if state == WAIT_HISTORY_QUERY:
            candidates = self.repository.search_courses(text)
            self.repository.set_session(user_id, READY, {})
            if not candidates:
                await self.send_message(chat_id, text_message("Курс не найден. Попробуй другое название.", back_button()))
                return
            rows = [
                [callback_button(item["name"][:55], f"history:course:{item['id']}")]
                for item in candidates
            ]
            rows.append([callback_button("⬅️ В меню", "menu:home")])
            await self.send_message(chat_id, text_message("Выбери найденный курс:", keyboard(rows)))
            return
        if state == WAIT_EDIT_GOAL:
            if len(text) < 3:
                await self.send_message(chat_id, text_message("Опиши цель хотя бы несколькими словами."))
                return
            self.repository.update_profile_field(user_id, "goal", text[:2000])
            self.repository.set_session(user_id, READY, {})
            await self.send_message(chat_id, main_menu("✅ Цель обновлена."))
            return
        if state == WAIT_EDIT_EXPERIENCE:
            if len(text) < 3:
                await self.send_message(chat_id, text_message("Опиши опыт хотя бы несколькими словами."))
                return
            self.repository.update_profile_field(user_id, "experience", text[:4000])
            self.repository.set_session(user_id, READY, {})
            await self.send_message(chat_id, main_menu("✅ Опыт обновлён."))
            return
        await self.handle_agent_question(user_id, chat_id, text)

    async def handle_callback(self, update: dict[str, Any], user_id: str) -> None:
        callback = update.get("callback") or {}
        callback_id = callback.get("callback_id")
        payload = callback.get("payload") or ""
        if not callback_id:
            return

        if payload == "auth:self" or payload.startswith("auth:synthetic:"):
            session = self.repository.get_session(user_id)
            data = dict((session or {}).get("data") or {})
            phone = data.get("phone")
            if not phone:
                await self.answer_callback(callback_id, contact_prompt())
                return
            if payload == "auth:self":
                resume_state = data.pop("_resume_state", WAIT_NAME)
                if resume_state not in REGISTRATION_STATES:
                    resume_state = WAIT_NAME
                self.repository.set_session(user_id, resume_state, data)
                await self.answer_callback(callback_id, self.registration_prompt(resume_state))
                return
            try:
                synthetic_user_id = int(payload.rsplit(":", 1)[1])
                self.repository.activate_synthetic_profile(user_id, phone, synthetic_user_id)
            except (TypeError, ValueError) as error:
                logging.warning("Synthetic profile selection failed for user %s: %s", user_id, error)
                await self.answer_callback(
                    callback_id,
                    text_message("Не удалось выбрать профиль. Попробуй другой вариант.", self.synthetic_profile_prompt()["attachments"][0]),
                )
                return
            self.repository.set_session(user_id, READY, {})
            await self.answer_callback(
                callback_id,
                main_menu("✅ Профиль найден. Добро пожаловать! Оценки и расписание уже загружены."),
            )
            return

        if payload.startswith("reg:"):
            session = self.repository.get_session(user_id)
            if not session or not (session.get("data") or {}).get("phone"):
                await self.answer_callback(callback_id, contact_prompt())
                return
        if payload.startswith("reg:university:"):
            value = payload.rsplit(":", 1)[1]
            university_id = None if value == "none" else int(value)
            if university_id is None:
                self.repository.update_session_data(
                    user_id,
                    WAIT_CUSTOM_UNIVERSITY,
                    university_id=None,
                    faculty_id=None,
                    specialty_id=None,
                    group_id=None,
                )
                await self.answer_callback(callback_id, self.registration_prompt(WAIT_CUSTOM_UNIVERSITY))
            else:
                faculties = self.repository.list_faculties(university_id)
                if not faculties:
                    self.repository.update_session_data(
                        user_id, WAIT_YEAR, university_id=university_id,
                        faculty_id=None, specialty_id=None, group_id=None,
                    )
                    await self.answer_callback(
                        callback_id,
                        text_message(
                            "Для этого университета пока нет списка факультетов. Продолжим без него.",
                            self.year_prompt()["attachments"][0],
                        ),
                    )
                    return
                self.repository.update_session_data(user_id, WAIT_FACULTY, university_id=university_id)
                await self.answer_callback(callback_id, self.faculty_prompt(university_id))
            return
        if payload.startswith("reg:faculty:"):
            session_data = dict((self.repository.get_session(user_id) or {}).get("data") or {})
            value = payload.rsplit(":", 1)[1]
            faculty_id = None if value == "none" else int(value)
            university_id = session_data.get("university_id")
            if faculty_id is None or university_id is None:
                self.repository.update_session_data(
                    user_id, WAIT_YEAR, faculty_id=None, specialty_id=None, group_id=None
                )
                await self.answer_callback(callback_id, self.year_prompt())
            else:
                specialties = self.repository.list_specialties(university_id, faculty_id)
                if not specialties:
                    self.repository.update_session_data(
                        user_id, WAIT_CUSTOM_SPECIALTY, faculty_id=faculty_id,
                        specialty_id=None, group_id=None,
                    )
                    await self.answer_callback(callback_id, self.registration_prompt(WAIT_CUSTOM_SPECIALTY))
                else:
                    self.repository.update_session_data(user_id, WAIT_SPECIALTY, faculty_id=faculty_id)
                    await self.answer_callback(callback_id, self.specialty_prompt(university_id, faculty_id))
            return
        if payload.startswith("reg:specialty:"):
            session_data = dict((self.repository.get_session(user_id) or {}).get("data") or {})
            value = payload.rsplit(":", 1)[1]
            specialty_id = None if value == "none" else int(value)
            university_id = session_data.get("university_id")
            faculty_id = session_data.get("faculty_id")
            if specialty_id is None or university_id is None or faculty_id is None:
                self.repository.update_session_data(
                    user_id, WAIT_YEAR, specialty_id=None, group_id=None
                )
                await self.answer_callback(callback_id, self.year_prompt())
            else:
                self.repository.update_session_data(
                    user_id, WAIT_GROUP, specialty_id=specialty_id
                )
                await self.answer_callback(
                    callback_id,
                    self.group_prompt(university_id, faculty_id, specialty_id),
                )
            return
        if payload.startswith("reg:group:"):
            value = payload.rsplit(":", 1)[1]
            group_id = None if value == "none" else int(value)
            self.repository.update_session_data(user_id, WAIT_YEAR, group_id=group_id)
            await self.answer_callback(callback_id, self.year_prompt())
            return
        if payload.startswith("reg:year:"):
            year = int(payload.rsplit(":", 1)[1])
            self.repository.update_session_data(user_id, WAIT_GOAL, study_year=year)
            await self.answer_callback(callback_id, self.registration_prompt(WAIT_GOAL))
            return
        if payload == "reset:confirm":
            self.repository.reset_registration(user_id)
            await self.answer_callback(
                callback_id,
                text_message(
                    "Сначала снова подтверди номер телефона.",
                    contact_prompt()["attachments"][0],
                ),
            )
            return
        if not self.repository.is_registered(user_id):
            await self.answer_callback(callback_id, text_message("Сначала закончи регистрацию."))
            return
        if payload == "menu:home":
            session_data = dict(
                (self.repository.get_session(user_id) or {}).get("data") or {}
            )
            context = session_data.get("recommendation_context")
            self.repository.set_session(
                user_id,
                READY,
                {"recommendation_context": context} if context else {},
            )
            await self.answer_callback(callback_id, main_menu())
        elif payload == "menu:profile":
            await self.answer_callback(callback_id, await self.profile_body(user_id))
        elif payload == "profile:edit_goal":
            self.repository.set_session(user_id, WAIT_EDIT_GOAL, {})
            await self.answer_callback(callback_id, text_message("Напиши новую учебную или профессиональную цель."))
        elif payload == "profile:edit_experience":
            self.repository.set_session(user_id, WAIT_EDIT_EXPERIENCE, {})
            await self.answer_callback(callback_id, text_message("Опиши свой текущий опыт: технологии, предметы и пройденные курсы."))
        elif payload == "menu:recommend":
            await self.answer_callback(
                callback_id,
                text_message(
                    "🎯 Напиши вопрос обычным сообщением.\n\nНапример: «Хочу изучить SQL для анализа данных» или «Что мне пройти дальше?»",
                    back_button(),
                ),
            )
        elif payload == "menu:history":
            await self.answer_callback(callback_id, self.history_body(user_id))
        elif payload == "menu:schedule":
            await self.answer_callback(callback_id, self.schedule_body(user_id))
        elif payload == "menu:reset":
            await self.answer_callback(
                callback_id,
                text_message(
                    "Перезапустить регистрацию?",
                    keyboard([[callback_button("Да", "reset:confirm")], [callback_button("Отмена", "menu:home")]]),
                ),
            )
        elif payload == "history:add":
            self.repository.set_session(user_id, WAIT_HISTORY_QUERY, {})
            await self.answer_callback(callback_id, text_message("Напиши название курса, который хочешь добавить."))
        elif payload == "history:progress":
            courses = self.repository.list_progress_courses(user_id)
            if not courses:
                await self.answer_callback(
                    callback_id,
                    text_message(
                        "Нет курсов, для которых можно обновить прогресс. Сначала добавь курс в план.",
                        back_button(),
                    ),
                )
                return
            rows = [
                [
                    callback_button(
                        f"{item['progress_percent']}% · {item['name'][:42]}",
                        f"progress:course:{item['course_id']}",
                    )
                ]
                for item in courses[:20]
            ]
            rows.append([callback_button("⬅️ К истории", "menu:history")])
            await self.answer_callback(
                callback_id,
                text_message("Выбери курс, прогресс которого изменился:", keyboard(rows)),
            )
        elif payload == "history:remove":
            courses = self.repository.list_progress_courses(user_id)
            if not courses:
                await self.answer_callback(
                    callback_id,
                    text_message("В плане нет курсов, которые можно удалить.", back_button()),
                )
                return
            rows = [
                [callback_button(f"🗑 {item['name'][:42]}", f"history:remove:course:{item['course_id']}")]
                for item in courses[:20]
            ]
            rows.append([callback_button("⬅️ К истории", "menu:history")])
            await self.answer_callback(
                callback_id,
                text_message("Выбери курс для удаления из плана. Завершённые курсы остаются в истории.", keyboard(rows)),
            )
        elif payload.startswith("history:remove:course:"):
            course_id = int(payload.rsplit(":", 1)[1])
            await self.answer_callback(
                callback_id,
                text_message(
                    "Удалить курс из плана и его прогресс? Это действие нельзя отменить.",
                    keyboard([
                        [callback_button("🗑 Удалить", f"history:remove:confirm:{course_id}")],
                        [callback_button("Отмена", "menu:history")],
                    ]),
                ),
            )
        elif payload.startswith("history:remove:confirm:"):
            course_id = int(payload.rsplit(":", 1)[1])
            try:
                self.repository.remove_course_from_plan(user_id, course_id)
            except ValueError as error:
                await self.answer_callback(callback_id, text_message(str(error), back_button()))
                return
            await self.answer_callback(callback_id, self.history_body(user_id))
        elif payload.startswith("progress:course:"):
            course_id = int(payload.rsplit(":", 1)[1])
            await self.answer_callback(
                callback_id,
                text_message(
                    "Какой этап курса достигнут?",
                    keyboard(
                        [
                            [
                                callback_button("25%", f"progress:set:{course_id}:25"),
                                callback_button("50%", f"progress:set:{course_id}:50"),
                                callback_button("75%", f"progress:set:{course_id}:75"),
                            ],
                            [callback_button("✅ Курс завершён", f"progress:set:{course_id}:100")],
                            [callback_button("⏸ Поставить на паузу", f"progress:pause:{course_id}")],
                            [callback_button("⬅️ К истории", "menu:history")],
                        ]
                    ),
                ),
            )
        elif payload.startswith("progress:set:"):
            _, _, course_id, progress = payload.split(":", 3)
            self.repository.record_course_progress(
                user_id, int(course_id), progress_percent=int(progress)
            )
            await self.answer_callback(callback_id, self.history_body(user_id))
        elif payload.startswith("progress:pause:"):
            course_id = int(payload.rsplit(":", 1)[1])
            self.repository.record_course_progress(user_id, course_id, paused=True)
            await self.answer_callback(callback_id, self.history_body(user_id))
        elif payload.startswith("history:course:"):
            course_id = int(payload.rsplit(":", 1)[1])
            await self.answer_callback(
                callback_id,
                text_message(
                    "Какой статус установить?",
                    keyboard(
                        [
                            [callback_button("✅ Завершён", f"history:set:{course_id}:completed")],
                            [callback_button("▶️ Прохожу", f"history:set:{course_id}:in_progress")],
                            [callback_button("📌 В планах", f"history:set:{course_id}:selected")],
                        ]
                    ),
                ),
            )
        elif payload.startswith("history:set:"):
            _, _, course_id, status = payload.split(":", 3)
            self.repository.set_course_status(user_id, int(course_id), status)
            await self.answer_callback(callback_id, self.history_body(user_id))
        elif payload.startswith("plan:add:"):
            course_id = int(payload.rsplit(":", 1)[1])
            self.repository.set_course_status(user_id, course_id, "selected")
            await self.answer_callback(callback_id, main_menu("📌 Курс добавлен в план."))
        else:
            await self.answer_callback(callback_id, main_menu("Неизвестная команда."))

    async def handle_update(self, update: dict[str, Any]) -> None:
        user_id, chat_id = self.update_identity(update)
        if not user_id:
            logging.warning("Update without user id: %s", update.get("update_type"))
            return
        lock = self.user_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            try:
                if update.get("update_type") == "message_callback":
                    await self.handle_callback(update, user_id)
                elif update.get("update_type") == "bot_started" and chat_id is not None:
                    await self.request_phone(user_id, chat_id)
                elif update.get("update_type") == "message_created" and chat_id is not None:
                    await self.handle_text(update, user_id, chat_id)
            except httpx.HTTPStatusError as error:
                logging.error("MAX API error %s: %s", error.response.status_code, error.response.text[:500])
            except Exception:
                logging.exception("Failed to handle update for user %s", user_id)
                if chat_id is not None:
                    try:
                        await self.send_message(chat_id, text_message("Произошла ошибка. Попробуй ещё раз."))
                    except Exception:
                        logging.exception("Could not send error message")

    async def run(self) -> None:
        me = await self.get_me()
        logging.info("Bot @%s started. Stop with Ctrl+C", me.get("username", "unknown"))
        while True:
            try:
                updates = await self.get_updates()
                for update in updates:
                    task = asyncio.create_task(self.handle_update(update))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
            except (httpx.TimeoutException, httpx.NetworkError):
                logging.warning("MAX connection lost; retrying in 3 seconds")
                await asyncio.sleep(3)
            except httpx.HTTPStatusError as error:
                logging.error("MAX polling error %s: %s", error.response.status_code, error.response.text[:500])
                await asyncio.sleep(5)


async def main() -> None:
    load_dotenv(PROJECT_DIR / ".env")
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    if not token or token == "ваш_токен_бота":
        raise SystemExit("Set MAX_BOT_TOKEN in .env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    bot = MaxBot(token)
    try:
        await bot.run()
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")
