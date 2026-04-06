# meta developer: @Loranger_r

from telethon.tl.types import Message
from telethon.extensions import html
from .. import loader, utils


@loader.tds
class BroadcastOnceMod(loader.Module):
    """Рассылка сообщения по добавленным чатам"""

    strings = {"name": "BroadcastOnce"}

    def _get_messages(self):
        data = self.get("bc_message", None)
        if isinstance(data, dict):
            if "html" in data:
                return {"default": data}
            if any(isinstance(v, dict) for v in data.values()):
                return data
        return {}

    def _set_messages(self, messages: dict):
        self.set("bc_message", messages)

    def _get_chats(self):
        chats = self.get("bc_chats", [])
        return chats if isinstance(chats, list) else []

    def _set_chats(self, chats):
        self.set("bc_chats", chats)

    def _find_chat(self, chats, chat_id):
        for item in chats:
            if item.get("id") == chat_id:
                return item
        return None

    async def _resolve_chat(self, raw: str):
        raw = raw.strip()
        if not raw:
            return None

        if raw.lstrip("-").isdigit():
            return int(raw)

        if "t.me/c/" in raw:
            try:
                part = raw.split("t.me/c/", 1)[1].split("/", 1)[0]
                if part.isdigit():
                    return int(f"-100{part}")
            except Exception:
                return None

        try:
            entity = await self._client.get_entity(raw)
            return int(getattr(entity, "id", 0) or 0)
        except Exception:
            return None

    async def _get_chat_title(self, chat_id, fallback: str = ""):
        try:
            entity = await self._client.get_entity(chat_id)
            title = getattr(entity, "title", None) or getattr(entity, "username", None)
            return title or fallback
        except Exception:
            return fallback

    @loader.command()
    async def bcadd(self, message: Message):
        """Добавить чат в рассылку. Без аргументов — добавить текущий чат (команда удалится)"""
        args = utils.get_args_raw(message)
        chats = self._get_chats()

        if not args:
            chat_id = int(getattr(message, "chat_id", 0) or 0)
            if not chat_id:
                return
            if not self._find_chat(chats, chat_id):
                title = ""
                if getattr(message, "chat", None):
                    title = getattr(message.chat, "title", "") or getattr(message.chat, "username", "")
                if not title:
                    title = await self._get_chat_title(chat_id, "")
                chats.append({"id": chat_id, "title": title})
                self._set_chats(chats)
            try:
                await message.delete()
            except Exception:
                pass
            return

        chat_id = await self._resolve_chat(args)
        if not chat_id:
            return await utils.answer(message, "<b>❌ Не смог найти чат по ссылке/ID.</b>")

        if self._find_chat(chats, chat_id):
            return await utils.answer(message, "<b>ℹ️ Этот чат уже добавлен.</b>")

        title = await self._get_chat_title(chat_id, "")
        chats.append({"id": chat_id, "title": title})
        self._set_chats(chats)
        await utils.answer(message, f"<b>✅ Чат добавлен:</b> <code>{chat_id}</code> {title}")

    @loader.command()
    async def bcrem(self, message: Message):
        """Удалить чат из рассылки. Без аргументов — удалить текущий чат"""
        args = utils.get_args_raw(message)
        chats = self._get_chats()

        if not args:
            chat_id = int(getattr(message, "chat_id", 0) or 0)
        else:
            chat_id = await self._resolve_chat(args)

        if not chat_id:
            return await utils.answer(message, "<b>❌ Не смог найти чат.</b>")

        new_chats = [c for c in chats if c.get("id") != chat_id]
        if len(new_chats) == len(chats):
            return await utils.answer(message, "<b>ℹ️ Этого чата нет в списке.</b>")

        self._set_chats(new_chats)
        await utils.answer(message, f"<b>✅ Удалил чат:</b> <code>{chat_id}</code>")

    @loader.command()
    async def bclist(self, message: Message):
        """Показать список чатов для рассылки"""
        chats = self._get_chats()
        if not chats:
            return await utils.answer(message, "<b>ℹ️ Список чатов пуст.</b>")

        lines = ["<b>📬 Чаты для рассылки:</b>"]
        for idx, item in enumerate(chats, 1):
            chat_id = item.get("id")
            title = item.get("title") or ""
            if not title:
                title = await self._get_chat_title(chat_id, "")
                item["title"] = title
            title_part = f" — {title}" if title else ""
            lines.append(f"{idx}. <code>{chat_id}</code>{title_part}")

        self._set_chats(chats)
        await utils.answer(message, "\n".join(lines))

    @loader.command()
    async def bcclear(self, message: Message):
        """Очистить список чатов для рассылки"""
        self._set_chats([])
        await utils.answer(message, "<b>✅ Список чатов очищен.</b>")

    @loader.command()
    async def bcset(self, message: Message):
        """Сохранить сообщение для рассылки (ответом на сообщение). Можно указать ключ"""
        key = utils.get_args_raw(message).strip() or "default"
        reply = await message.get_reply_message()
        if not reply:
            return await utils.answer(message, "<b>❌ Ответьте на сообщение.</b>")

        text = reply.message or ""
        entities = reply.entities or []
        if not text:
            return await utils.answer(message, "<b>❌ В сообщении нет текста.</b>")

        html_text = html.unparse(text, entities) if entities else text
        messages = self._get_messages()
        messages[key] = {"html": html_text}
        self._set_messages(messages)
        if key == "default":
            await utils.answer(message, "<b>✅ Сообщение для рассылки сохранено.</b>")
        else:
            await utils.answer(message, f"<b>✅ Сообщение сохранено:</b> <code>{key}</code>")

    @loader.command()
    async def bcinfo(self, message: Message):
        """Показать информацию о сохранённом сообщении"""
        messages = self._get_messages()
        if not messages:
            return await utils.answer(message, "<b>ℹ️ Сообщение для рассылки не задано.</b>")

        keys = ", ".join(sorted(messages.keys()))
        data = messages.get("default") or next(iter(messages.values()))
        html_text = data.get("html", "")
        preview = html_text[:200].replace("\n", " ")
        await utils.answer(
            message,
            "<b>📝 Сообщение для рассылки задано.</b>\n"
            f"<b>Ключи:</b> <code>{keys}</code>\n"
            f"<b>Длина (пример):</b> <code>{len(html_text)}</code>\n"
            f"<b>Превью (пример):</b> <code>{preview}</code>"
        )

    @loader.command()
    async def bckeys(self, message: Message):
        """Показать список ключей сохранённых сообщений"""
        messages = self._get_messages()
        if not messages:
            return await utils.answer(message, "<b>ℹ️ Ключи не заданы.</b>")

        keys = sorted(messages.keys())
        lines = ["<b>🔑 Ключи сообщений:</b>"]
        for idx, key in enumerate(keys, 1):
            lines.append(f"{idx}. <code>{key}</code>")
        await utils.answer(message, "\n".join(lines))

    @loader.command()
    async def bcdel(self, message: Message):
        """Удалить сохранённое сообщение по ключу"""
        key = utils.get_args_raw(message).strip()
        if not key:
            return await utils.answer(message, "<b>❌ Укажите ключ.</b>")

        messages = self._get_messages()
        if key not in messages:
            return await utils.answer(message, "<b>ℹ️ Такого ключа нет.</b>")

        messages.pop(key, None)
        self._set_messages(messages)
        await utils.answer(message, f"<b>✅ Ключ удалён:</b> <code>{key}</code>")

    async def _send_to_chat(self, chat_id: int, data: dict):
        html_text = data.get("html", "")
        if not html_text:
            return False
        try:
            await self._client.send_message(
                chat_id,
                html_text,
                parse_mode="html",
                link_preview=False,
            )
            return True
        except Exception:
            return False

    @loader.command()
    async def bcsend(self, message: Message):
        """Отправить сохранённое сообщение во все добавленные чаты (1 раз)"""
        key = utils.get_args_raw(message).strip() or "default"
        messages = self._get_messages()
        data = messages.get(key)
        if not data:
            return await utils.answer(message, "<b>❌ Сообщение для рассылки не задано.</b>")

        chats = self._get_chats()
        if not chats:
            return await utils.answer(message, "<b>❌ Список чатов пуст.</b>")

        ok = 0
        fail = []
        for item in chats:
            chat_id = item.get("id")
            if await self._send_to_chat(chat_id, data):
                ok += 1
            else:
                fail.append(chat_id)

        if fail:
            fail_list = ", ".join(str(x) for x in fail)
            await utils.answer(
                message,
                f"<b>✅ Отправлено:</b> <code>{ok}</code>\n"
                f"<b>❌ Ошибки:</b> <code>{len(fail)}</code>\n"
                f"<b>Чаты:</b> <code>{fail_list}</code>"
            )
        else:
            await utils.answer(message, f"<b>✅ Отправлено во все чаты:</b> <code>{ok}</code>")

    @loader.command()
    async def bcsendhere(self, message: Message):
        """Отправить сохранённое сообщение в текущий чат"""
        key = utils.get_args_raw(message).strip() or "default"
        messages = self._get_messages()
        data = messages.get(key)
        if not data:
            return await utils.answer(message, "<b>❌ Сообщение для рассылки не задано.</b>")

        chat_id = int(getattr(message, "chat_id", 0) or 0)
        if not chat_id:
            return await utils.answer(message, "<b>❌ Не смог определить чат.</b>")

        await self._send_to_chat(chat_id, data)
        try:
            await message.delete()
        except Exception:
            pass
