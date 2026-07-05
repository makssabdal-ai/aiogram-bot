import asyncio
import json
import re
from datetime import datetime
from html import escape, unescape
from os import getenv
from typing import Any

import aiohttp
from dotenv import dotenv_values

from database.db import Database
from utils.consent import CONSENT_DOCUMENT_VERSION, consent_document_url, vk_consent_text
from utils.constants import CAKE_NAMES, LOGISTICS, SIZES
from utils.validators import Validators
from vk_bot import keyboards
from vk_bot.client import VKClient


WELCOME_HTML = (
    "<b>Привет, {name}!</b>\n"
    "Я <i>Poli</i>, новый телеграмм-бот.\n\n"
    "Зачем я нужен? Отвечу просто — для удобства коммуникации и связи) 😉\n\n"
    "Что здесь есть?\n\n"
    "  • Каталог товаров \n"
    "  • Мои работы \n"
    "  • Ваши отзывы \n"
    "  • Мои контакты \n"
    "  • И возможность сделать заказ прямо здесь!\n\n"
    "Устраивайтесь поудобнее и давайте начнем наше сладкое путешествие! 🎂✨ \n\n"
    "<i>created by Smirnov</i>"
)

ABOUT_HTML = (
    "Привет-привет! Я Полина. Пеку торты не по учебникам, а по любви 💗✨\n"
    "А этот бот — мой маленький помощник 🤖\n\n"
    "Первый раз испекла торт больше пяти лет назад — и затянуло 😊🍰\n"
    "На заказ работаю около двух лет, и за это время собрала не только навыки, "
    "но и искренние «спасибо» от клиентов. 🙏💕"
)
ABOUT_VK_PHOTO_ID = "photo491400521_457250277_1573833bd4fde8f0aa"

CONTACTS_HTML = (
    "Со мной можно связаться по следующим контактам:\n\n"
    "🔹 ТГ-аккаунт: @Sewwwqp\n"
    "🔹 Страница Вконтакте: https://vk.com/polya_smi\n"
    "🔹 Телеграм-канал: https://t.me/tortsm\n"
    "🔹 Сообщество Вконтакте: https://vk.com/club235221265\n\n"
    "Буду рада помочь Вам! 🤗"
)


class VKCakeBot:
    def __init__(self, client: VKClient, db: Database):
        self.client = client
        self.db = db
        self.states: dict[int, str] = {}
        self.data: dict[int, dict[str, Any]] = {}
        self.greeted_users: set[int] = set()
        self.media_id_batches: dict[int, list[dict[str, str | None]]] = {}
        self.media_id_tasks: dict[int, asyncio.Task] = {}
        self.works_offsets: dict[int, int] = {}
        self.works_locks: dict[int, asyncio.Lock] = {}

    async def handle_update(self, update: dict[str, Any]):
        if update.get("type") == "message_event":
            await self.handle_message_event(update)
            return
        if update.get("type") != "message_new":
            return

        message = update.get("object", {}).get("message", {})
        user_id = message.get("from_id")
        peer_id = message.get("peer_id")
        if not user_id or not peer_id:
            return

        text = (message.get("text") or "").strip()
        payload = self._get_payload(message)
        command = payload.get("cmd") if payload else self._text_to_command(text)
        attachments = message.get("attachments") or []

        if command == "back":
            await self.show_main_menu(peer_id, user_id, greeting=False)
            return

        if command:
            handled = await self.handle_command(peer_id, user_id, command, attachments)
            if handled:
                return

        if attachments and not self.states.get(user_id):
            media_items = self._vk_media_items(attachments)
            if media_items:
                self._queue_media_ids(peer_id, media_items)
                return

        await self.handle_state(peer_id, user_id, text, attachments)

    async def handle_message_event(self, update: dict[str, Any]):
        event = update.get("object", {})
        user_id = event.get("user_id")
        peer_id = event.get("peer_id")
        payload = self._normalize_payload(event.get("payload"))

        if not user_id or not peer_id:
            return

        command = payload.get("cmd")
        if command == "back":
            await self.show_main_menu(peer_id, user_id, greeting=False)
            return
        if command:
            await self.handle_command(peer_id, user_id, command, attachments=[])
            return

        print(f"[VK WARN] Callback event without command payload: {payload}")

    async def ensure_personal_data_consent(self, peer_id: int, user_id: int) -> bool:
        db_user_id = -user_id
        if await self.db.has_personal_data_consent(db_user_id):
            return True

        user_name = await self.get_vk_user_name(user_id)
        await self.db.add_user(telegram_id=db_user_id, fullname=user_name, username=f"vk.com/id{user_id}")
        await self.send_vk(peer_id, vk_consent_text(), keyboard=keyboards.personal_data_consent_menu())
        return False

    async def accept_personal_data_consent(self, peer_id: int, user_id: int):
        user_name = await self.get_vk_user_name(user_id)
        await self.db.set_personal_data_consent(
            telegram_id=-user_id,
            fullname=user_name,
            username=f"vk.com/id{user_id}",
            platform="vk",
            document=f"{CONSENT_DOCUMENT_VERSION}: {consent_document_url()}",
        )
        await self.start_order(peer_id, user_id)

    async def handle_command(
        self,
        peer_id: int,
        user_id: int,
        command: str,
        attachments: list[dict[str, Any]],
    ) -> bool:
        if command in ("start", "help"):
            await self.show_main_menu(peer_id, user_id, greeting=True)
            return True
        if command == "catalog":
            await self.show_catalog(peer_id)
            return True
        if command.startswith("product:"):
            await self.show_product(peer_id, command)
            return True
        if command == "view_works":
            await self.show_works(peer_id, user_id)
            return True
        if command == "works_more":
            await self.show_works_chunk(peer_id, user_id)
            return True
        if command == "reviews":
            await self.show_reviews(peer_id)
            return True
        if command == "about":
            await self.send_vk(peer_id, ABOUT_HTML, keyboard=keyboards.back_menu(), attachment=ABOUT_VK_PHOTO_ID)
            return True
        if command == "contact_me":
            await self.send_vk(peer_id, CONTACTS_HTML, keyboard=keyboards.back_menu())
            return True
        if command == "make_order":
            if not await self.ensure_personal_data_consent(peer_id, user_id):
                return True
            await self.start_order(peer_id, user_id)
            return True
        if command == "personal_data_consent_accept":
            await self.accept_personal_data_consent(peer_id, user_id)
            return True
        if command == "edit_order":
            await self.start_order(peer_id, user_id)
            return True

        state = self.states.get(user_id)
        if state == "cake" and command in CAKE_NAMES:
            await self.set_cake(peer_id, user_id, command)
            return True
        if state == "size" and command in SIZES:
            await self.set_size(peer_id, user_id, command)
            return True
        if state == "logistics" and command in LOGISTICS:
            await self.set_logistics(peer_id, user_id, command)
            return True
        if state in ("media", "additional_info") and command == "skip":
            await self.skip_optional_step(peer_id, user_id)
            return True
        if state == "date" and command.startswith("date_page:"):
            await self.show_date_picker(peer_id, int(command.split(":", 1)[1]))
            return True
        if state == "date" and command.startswith("date_pick:"):
            await self.set_date(peer_id, user_id, command.split(":", 1)[1])
            return True
        if command == "confirm_order":
            await self.confirm_order(peer_id, user_id)
            return True

        return False

    async def handle_state(
        self,
        peer_id: int,
        user_id: int,
        text: str,
        attachments: list[dict[str, Any]],
    ):
        state = self.states.get(user_id)
        if not state:
            await self.send_vk(
                peer_id,
                "Извините, я не знаю такой команды.\nВведите /help для вызова меню.",
                keyboard=keyboards.main_menu(),
            )
            return

        if state == "fullname":
            is_valid, result = Validators.validate_fullname(text)
            if not is_valid:
                await self.send_vk(peer_id, result)
                return
            self.data[user_id]["fullname"] = result
            self.states[user_id] = "phone_number"
            await self.send_vk(peer_id, "Теперь введите Ваш номер телефона:")
            return

        if state == "phone_number":
            is_valid, result = Validators.validate_phone(text)
            if not is_valid:
                await self.send_vk(peer_id, result)
                return
            self.data[user_id]["phone_number"] = result
            self.states[user_id] = "account"
            await self.send_vk(peer_id, "Теперь напишите ссылку на Ваш ВК или юзернейм в ТГ:")
            return

        if state == "account":
            is_valid, response = Validators.validate_social_account(text)
            if not is_valid:
                await self.send_vk(peer_id, response)
                return
            self.data[user_id]["account"] = text
            self.states[user_id] = "cake"
            await self.send_vk(
                peer_id,
                "Теперь выберите торт из предложенных:",
                keyboard=keyboards.cake_menu(),
            )
            return

        if state == "date":
            await self.send_vk(
                peer_id,
                "Выберите дату с помощью календаря ниже:",
                keyboard=keyboards.date_menu(),
            )
            return

        if state == "media":
            media = self._first_vk_media(attachments)
            if not media:
                await self.send_vk(
                    peer_id,
                    "Пожалуйста, отправьте фото, видео или нажмите кнопку 'Пропустить'",
                    keyboard=keyboards.skip_menu(),
                )
                return
            self.data[user_id]["media_type"] = media["type"]
            self.data[user_id]["media"] = media["attachment"]
            self.data[user_id]["media_url"] = media.get("url")
            self.states[user_id] = "additional_info"
            await self.send_vk(
                peer_id,
                "Почти готово! Укажите дополнительную информацию (для доставки — точный адрес и время):",
                keyboard=keyboards.skip_menu(),
            )
            return

        if state == "additional_info":
            self.data[user_id]["additional_info"] = text if text else "Не указано"
            await self.send_order_summary(peer_id, user_id)

    async def show_main_menu(self, peer_id: int, user_id: int, greeting: bool):
        self.states.pop(user_id, None)
        self.data.pop(user_id, None)
        self.works_offsets.pop(user_id, None)
        self.works_locks.pop(user_id, None)
        user_name = await self.get_vk_user_name(user_id)
        await self.db.add_user(telegram_id=-user_id, fullname=user_name, username=f"vk.com/id{user_id}")

        if greeting:
            self.greeted_users.add(user_id)
            await self.send_vk(peer_id, WELCOME_HTML.format(name=user_name), keyboard=keyboards.main_menu())
            return

        await self.send_vk(peer_id, "Главное меню:", keyboard=keyboards.main_menu())

    async def show_catalog(self, peer_id: int):
        items = await self.db.get_catalog()
        if not items:
            await self.send_vk(peer_id, "Каталог пока пуст 😢", keyboard=keyboards.back_menu())
            return
        await self.send_vk(
            peer_id,
            "🛍 <b>Каталог товаров:</b>\nВыберите интересующую позицию:",
            keyboard=keyboards.catalog_menu(items),
        )

    async def show_product(self, peer_id: int, command: str):
        product_id = int(command.split(":", 1)[1])
        item = await self.db.get_product(product_id)
        if not item:
            await self.send_vk(peer_id, "Товар не найден.", keyboard=keyboards.back_menu())
            return
        attachment = self._catalog_vk_attachment(item)
        await self.send_vk(
            peer_id,
            f"<b>{item['title']}</b>\n\n{item['description']}",
            keyboard=keyboards.product_back_menu(),
            attachment=attachment,
        )

    async def show_works(self, peer_id: int, user_id: int):
        self.works_offsets[user_id] = 0
        await self.send_vk(peer_id, "Здесь Вы можете ознакомится с моими работами")
        await self.show_works_chunk(peer_id, user_id)

    async def show_works_chunk(self, peer_id: int, user_id: int):
        lock = self.works_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            await self._show_works_chunk_locked(peer_id, user_id)

    async def _show_works_chunk_locked(self, peer_id: int, user_id: int):
        works = await self.db.get_works()
        if not works:
            await self.send_vk(peer_id, "Пока нет доступных работ 😢", keyboard=keyboards.back_menu())
            return

        vk_media = [work for work in works if self._is_vk_attachment(work.get("vk_file_id"))]
        if not vk_media:
            await self.send_vk(
                peer_id,
                "📸 Наши готовые работы\n\n"
                "В базе пока нет VK-вложений для отправки в сообщения. "
                "Telegram file_id не отображаются во ВКонтакте.",
                keyboard=keyboards.back_menu(),
            )
            return

        offset = self.works_offsets.get(user_id, 0)
        chunk = vk_media[offset:offset + 10]
        if not chunk:
            await self.send_vk(peer_id, "Вы посмотрели все доступные работы.", keyboard=keyboards.works_menu(False))
            return

        attachments = ",".join(work["vk_file_id"] for work in chunk)
        try:
            await self.send_vk(peer_id, "", attachment=attachments)
        except Exception as exc:
            print(f"[VK WARN] Failed to send works chunk as one message: {exc}")
            for work in chunk:
                try:
                    await self.send_vk(peer_id, "📸", attachment=work["vk_file_id"])
                except Exception as item_exc:
                    print(f"[VK WARN] Failed to send work media {work.get('id')}: {item_exc}")

        next_offset = offset + len(chunk)
        self.works_offsets[user_id] = next_offset
        has_more = next_offset < len(vk_media)
        await self.send_vk(peer_id, f"Показано {next_offset} из {len(vk_media)}", keyboard=keyboards.works_menu(has_more))

    async def show_reviews(self, peer_id: int):
        reviews = await self.db.get_reviews()
        if not reviews:
            await self.send_vk(peer_id, "Пока нет отзывов 😢", keyboard=keyboards.back_menu())
            return

        vk_media = [review for review in reviews if self._is_vk_attachment(review.get("vk_file_id"))]
        if vk_media:
            for index in range(0, len(vk_media), 10):
                attachments = ",".join(review["vk_file_id"] for review in vk_media[index:index + 10])
                await self.send_vk(peer_id, "", attachment=attachments)
            await self.send_vk(peer_id, "Отзывы клиентов 💬", keyboard=keyboards.back_menu())
            return

        text_reviews = [r["text"] for r in reviews if r.get("text")]
        if text_reviews:
            await self.send_vk(peer_id, "Отзывы клиентов 💬\n\n" + "\n\n".join(text_reviews[:10]), keyboard=keyboards.back_menu())
            return

        await self.send_vk(
            peer_id,
            "Отзывы клиентов 💬\n\n"
            "В базе есть отзывы с Telegram file_id, но их нельзя напрямую отправить во ВКонтакте.",
            keyboard=keyboards.back_menu(),
        )

    async def start_order(self, peer_id: int, user_id: int):
        self.states[user_id] = "fullname"
        self.data[user_id] = {}
        await self.send_vk(
            peer_id,
            "Давайте создадим заявку Вашего заказа. Для начала введите Ваше ФИО:",
            keyboard=keyboards.back_menu(),
        )

    async def set_cake(self, peer_id: int, user_id: int, command: str):
        self.data[user_id]["cake"] = self.clean_html(CAKE_NAMES[command])
        self.states[user_id] = "size"
        await self.send_vk(peer_id, "Теперь выберите размер торта:", keyboard=keyboards.size_menu())

    async def set_size(self, peer_id: int, user_id: int, command: str):
        self.data[user_id]["size"] = self.clean_html(SIZES[command])
        self.states[user_id] = "date"
        await self.show_date_picker(peer_id, offset=0)

    async def show_date_picker(self, peer_id: int, offset: int = 0):
        await self.send_vk(
            peer_id,
            "Выберите дату, к которой нужно приготовить торт:",
            keyboard=keyboards.date_menu(offset),
        )

    async def set_date(self, peer_id: int, user_id: int, text: str):
        try:
            selected_date = datetime.strptime(text, "%d.%m.%Y").date()
        except ValueError:
            await self.send_vk(peer_id, "Введите дату в формате дд.мм.гггг, например 15.07.2026.")
            return

        is_valid, msg = Validators.validate_date(selected_date)
        if not is_valid:
            await self.send_vk(peer_id, msg)
            return

        formatted_date = selected_date.strftime("%d.%m.%Y")
        count = await self.db.count_orders_by_date(formatted_date)
        if count >= 3:
            await self.send_vk(
                peer_id,
                "Эта дата уже полностью занята (лимит 3 заказа). Пожалуйста, выберите другую дату.",
            )
            return

        self.data[user_id]["date_delivery"] = formatted_date
        self.states[user_id] = "logistics"
        await self.send_vk(peer_id, "Выберите способ доставки:", keyboard=keyboards.logistics_menu())

    async def set_logistics(self, peer_id: int, user_id: int, command: str):
        self.data[user_id]["logistics"] = self.clean_html(LOGISTICS[command])
        self.states[user_id] = "media"
        await self.send_vk(
            peer_id,
            "Вы можете отправить фото или видео примера:",
            keyboard=keyboards.skip_menu(),
        )

    async def skip_optional_step(self, peer_id: int, user_id: int):
        state = self.states.get(user_id)
        if state == "media":
            self.data[user_id]["media_type"] = None
            self.data[user_id]["media"] = None
            self.data[user_id]["media_url"] = None
            self.states[user_id] = "additional_info"
            await self.send_vk(
                peer_id,
                "Введите дополнительную информацию или пожелания (если есть):",
                keyboard=keyboards.skip_menu(),
            )
            return
        if state == "additional_info":
            self.data[user_id]["additional_info"] = "Не указано"
            await self.send_order_summary(peer_id, user_id)

    async def send_order_summary(self, peer_id: int, user_id: int):
        order = self.data[user_id]
        media_text = "Фото" if order.get("media_type") == "photo" else "Видео" if order.get("media_type") == "video" else "Не прикреплено"
        summary = (
            "📋 <b>Проверьте вашу заявку:</b>\n\n"
            f"👤 ФИО: {self.html_escape(order['fullname'])}\n"
            f"📞 Телефон: {self.html_escape(order['phone_number'])}\n"
            f"🌐 Аккаунт: {self.html_escape(order['account'])}\n"
            f"🎂 Торт: {self.html_escape(order['cake'])}\n"
            f"⚖️ Размер: {self.html_escape(order['size'])}\n"
            f"📅 Забронированная дата: {self.html_escape(order['date_delivery'])}\n"
            f"🚗 Доставка: {self.html_escape(order['logistics'])}\n"
            f"🖼 Пример: {media_text}\n"
            f"📝 Комментарий: {self.html_escape(order['additional_info'])}"
        )
        await self.send_vk(peer_id, summary, keyboard=keyboards.check_menu())

    async def confirm_order(self, peer_id: int, user_id: int):
        order = self.data.get(user_id)
        if not order:
            await self.send_vk(peer_id, "Ошибка сессии. Сформируйте заказ заново.")
            return

        await self.db.add_order(telegram_id=-user_id, data=order)
        order_text = (
            "🆕 <b>Новый заказ из VK!</b>\n\n"
            f"ФИО: {self.html_escape(order['fullname'])}\n"
            f"Телефон: {self.html_escape(order['phone_number'])}\n"
            f"Аккаунт: {self.html_escape(order['account'])}\n\n"
            f"Торт: {self.html_escape(order['cake'])}\n"
            f"Размер: {self.html_escape(order['size'])}\n"
            f"Забронированная дата: {self.html_escape(order['date_delivery'])}\n"
            f"Логистика: {self.html_escape(order['logistics'])}\n\n"
            f"Доп. информация:\n{self.html_escape(order['additional_info'])}"
        )
        await self.notify_telegram_admins(order_text, order)

        self.states.pop(user_id, None)
        self.data.pop(user_id, None)
        await self.send_vk(
            peer_id,
            "Заказ принят! Скоро я свяжусь с вами для подтверждения 😊",
            keyboard=keyboards.back_menu(),
        )

    async def send_vk(
        self,
        peer_id: int,
        text: str,
        keyboard: str | None = None,
        attachment: str | None = None,
    ):
        await self.client.send_message(
            peer_id=peer_id,
            text=self.render_vk_text(text),
            keyboard=keyboard,
            attachment=attachment if self._is_vk_attachment_list(attachment) else None,
        )

    def _queue_media_ids(self, peer_id: int, media_items: list[dict[str, str | None]]):
        self.media_id_batches.setdefault(peer_id, []).extend(media_items)
        task = self.media_id_tasks.get(peer_id)
        if task and not task.done():
            task.cancel()
        self.media_id_tasks[peer_id] = asyncio.create_task(self._flush_media_ids(peer_id))

    async def _flush_media_ids(self, peer_id: int):
        try:
            await asyncio.sleep(2)
            media_items = self.media_id_batches.pop(peer_id, [])
            self.media_id_tasks.pop(peer_id, None)
            if media_items:
                await self.send_vk(peer_id, self._vk_media_ids_text(media_items))
        except asyncio.CancelledError:
            return

    async def notify_telegram_admins(self, text: str, order: dict[str, Any]):
        token = self.env_value("BOT_TOKEN")
        admin_ids = self.telegram_admin_ids()
        if not token or not admin_ids:
            print("[VK ERROR] BOT_TOKEN or ADMIN_IDS is not configured; Telegram admin notification skipped")
            return

        async with aiohttp.ClientSession() as session:
            for admin_id in admin_ids:
                try:
                    await self.send_telegram_order(session, token, admin_id, text, order)
                except Exception as exc:
                    print(f"[VK ERROR] Failed to notify Telegram admin {admin_id}: {exc}")

    async def send_telegram_order(
        self,
        session: aiohttp.ClientSession,
        token: str,
        admin_id: int,
        text: str,
        order: dict[str, Any],
    ):
        media_url = order.get("media_url")
        media_type = order.get("media_type")
        vk_attachment = order.get("media")

        if media_url and media_type == "photo":
            await session.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                json={
                    "chat_id": admin_id,
                    "photo": media_url,
                    "caption": text,
                    "parse_mode": "HTML",
                },
            )
            return

        if media_url and media_type == "video":
            response = await session.post(
                f"https://api.telegram.org/bot{token}/sendVideo",
                json={
                    "chat_id": admin_id,
                    "video": media_url,
                    "caption": text,
                    "parse_mode": "HTML",
                },
            )
            data = await response.json(content_type=None)
            if data.get("ok"):
                return

        if vk_attachment:
            text = f"{text}\n\nVK-пример: {self.html_escape(vk_attachment)}"
            if media_url:
                text = f"{text}\nСсылка на медиа: {self.html_escape(media_url)}"

        await session.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": admin_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
        )

    @staticmethod
    def _get_payload(message: dict[str, Any]) -> dict[str, Any]:
        raw_payload = message.get("payload")
        return VKCakeBot._normalize_payload(raw_payload)

    @staticmethod
    def _normalize_payload(raw_payload: Any) -> dict[str, Any]:
        if not raw_payload:
            return {}
        if isinstance(raw_payload, dict):
            return raw_payload
        try:
            return json.loads(raw_payload)
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _text_to_command(text: str) -> str | None:
        normalized = " ".join(text.strip().lower().replace("ё", "е").split())
        if normalized in ("/start", "start", "старт", "меню", "начать"):
            return "start"
        if normalized in ("/help", "help", "помощь"):
            return "help"
        if normalized in (
            "согласен(на)",
            "я прочитал(а) и согласен(на)",
            "я прочитал и согласен",
            "я прочитала и согласна",
        ):
            return "personal_data_consent_accept"
        if normalized in ("каталог товаров 🛍", "каталог товаров", "каталог"):
            return "catalog"
        if normalized in ("мои работы 📸", "мои работы", "работы"):
            return "view_works"
        if normalized in ("отзывы 💬", "отзывы"):
            return "reviews"
        if normalized in ("написать мне ✉️", "написать мне"):
            return "contact_me"
        if normalized in ("обо мне 👩‍🍳", "обо мне"):
            return "about"
        if normalized in ("сделать заказ ✨", "сделать заказ"):
            return "make_order"
        if normalized == "показать еще":
            return "works_more"
        if normalized in ("в главное меню", "⬅️ в главное меню"):
            return "back"
        return None

    @staticmethod
    def _first_vk_media(attachments: list[dict[str, Any]]) -> dict[str, str | None] | None:
        media_items = VKCakeBot._vk_media_items(attachments)
        return media_items[0] if media_items else None

    @staticmethod
    def _vk_media_items(attachments: list[dict[str, Any]]) -> list[dict[str, str | None]]:
        media_items = []
        for attachment in attachments:
            kind = attachment.get("type")
            obj = attachment.get(kind, {})
            owner_id = obj.get("owner_id")
            item_id = obj.get("id")
            access_key = obj.get("access_key")
            if kind in ("photo", "video") and owner_id and item_id:
                value = f"{kind}{owner_id}_{item_id}"
                if access_key:
                    value += f"_{access_key}"
                media_items.append(
                    {
                        "type": kind,
                        "attachment": value,
                        "url": VKCakeBot._vk_media_url(kind, obj),
                    }
                )
        return media_items

    @staticmethod
    def _vk_media_ids_text(media_items: list[dict[str, str | None]]) -> str:
        lines = ["ID медиафайлов для VK:"]
        for index, item in enumerate(media_items, 1):
            lines.append(f"{index}. {item['attachment']}")
        return "\n".join(lines)

    @staticmethod
    def _vk_media_url(kind: str, obj: dict[str, Any]) -> str | None:
        if kind == "photo":
            sizes = obj.get("sizes") or []
            if not sizes:
                return None
            best = max(sizes, key=lambda item: item.get("width", 0) * item.get("height", 0))
            return best.get("url")
        if kind == "video":
            return obj.get("player")
        return None

    @staticmethod
    def _attachment_type(value: str) -> str | None:
        if value.startswith("photo"):
            return "photo"
        if value.startswith("video"):
            return "video"
        return None

    @staticmethod
    def _is_vk_attachment(value: str | None) -> bool:
        return bool(value and re.match(r"^(photo|video)-?\d+_\d+(?:_[A-Za-z0-9]+)?$", value))

    @staticmethod
    def _is_vk_attachment_list(value: str | None) -> bool:
        if not value:
            return False
        return all(VKCakeBot._is_vk_attachment(item.strip()) for item in value.split(","))

    @staticmethod
    def _catalog_vk_attachment(item: Any) -> str | None:
        value = item.get("vk_file_id")
        return value if VKCakeBot._is_vk_attachment(value) else None

    @staticmethod
    def render_vk_text(text: str) -> str:
        text = re.sub(r"</?b>", "", text)
        text = re.sub(r"</?i>", "", text)
        text = re.sub(r"<br\s*/?>", "\n", text)
        return unescape(re.sub(r"<[^>]*>", "", text))

    @staticmethod
    def clean_html(text: str) -> str:
        return unescape(re.sub(r"<[^>]*>", "", text or "")).strip()

    @staticmethod
    def html_escape(text: Any) -> str:
        return escape(str(text or ""), quote=False)

    @staticmethod
    def telegram_admin_ids() -> list[int]:
        raw = VKCakeBot.env_value("ADMIN_IDS", "")
        return [int(item) for item in raw.split(",") if item.strip().isdigit()]

    @staticmethod
    def env_value(name: str, default: str | None = None) -> str | None:
        value = getenv(name) or getenv(f"{name} ")
        if value:
            return value
        file_values = dotenv_values(".env")
        return file_values.get(name) or file_values.get(f"{name} ") or default

    async def get_vk_user_name(self, user_id: int) -> str:
        try:
            users = await self.client.api("users.get", user_ids=user_id)
        except Exception:
            return f"VK user {user_id}"
        if users:
            first_name = users[0].get("first_name")
            return first_name or f"VK user {user_id}"
        return f"VK user {user_id}"
