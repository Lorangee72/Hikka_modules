from .. import loader, utils
from telethon import errors
import asyncio, json, os, re
from datetime import datetime, timedelta

@loader.tds
class ChatStatsMod(loader.Module):
    strings = {
        "name": "ChatStats",
        "cs_scan_desc": "Сканировать чат",
        "cs_user_desc": "Статистика по пользователю",
        "cs_info_desc": "Общая статистика чата",
        "cs_clear_desc": "Удалить сохранение",
        "cs_twords_desc": "Общий топ слов"
    }

    file_template = "cs_{chat_id}.json"
    running = {}

    def _default_data(self):
        return {
            "messages_total": 0,
            "words": {},
            "reactions": {},
            "voices": 0,
            "rounds": 0,
            "stickers": 0,
            "images": 0,
            "videos": 0,
            "gifs": 0,
            "files": 0,
            "users": {}
        }

    def _load(self, chat_id):
        file = self.file_template.format(chat_id=chat_id)
        if not os.path.exists(file):
            return self._default_data()
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, chat_id, data):
        file = self.file_template.format(chat_id=chat_id)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    async def safe_edit(self, msg_obj, text):
        try:
            return await msg_obj.edit(text)
        except Exception:
            try:
                return await self.client.send_message(msg_obj.chat_id, text)
            except Exception:
                return msg_obj

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    async def _process_message(self, msg, data):
        data["messages_total"] += 1
        uid = str(msg.sender_id)

        if uid not in data["users"]:
            data["users"][uid] = {
                "words": {},
                "messages": 0,
                "images": 0,
                "videos": 0,
                "gifs": 0,
                "files": 0
            }

        if getattr(msg, "message", None):
            for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9']+", msg.message.lower()):
                data["words"][w] = data["words"].get(w, 0) + 1
                data["users"][uid]["words"][w] = data["users"][uid]["words"].get(w, 0) + 1

        data["users"][uid]["messages"] += 1

        if getattr(msg, "reactions", None):
            for r in msg.reactions.results:
                em = getattr(r.reaction, "emoticon", str(r.reaction))
                data["reactions"][em] = data["reactions"].get(em, 0) + r.count

        if getattr(msg, "media", None) and getattr(msg.media, "document", None):
            mime = getattr(msg.media.document, "mime_type", "")

            if "sticker" in mime:
                data["stickers"] += 1
            elif "audio/voice" in mime:
                data["voices"] += 1
            elif "video/round" in mime or "video/webm" in mime:
                data["rounds"] += 1
            elif mime.startswith("image/"):
                if mime == "image/gif":
                    data["gifs"] += 1
                    data["users"][uid]["gifs"] += 1
                else:
                    data["images"] += 1
                    data["users"][uid]["images"] += 1
            elif mime.startswith("video/"):
                data["videos"] += 1
                data["users"][uid]["videos"] += 1
            else:
                data["files"] += 1
                data["users"][uid]["files"] += 1

    async def _scan_chat(self, m, chat):
        chat_id = chat.id
        if self.running.get(chat_id, False):
            return await utils.answer(m, "⚠ Уже выполняется")

        self.running[chat_id] = True
        data = self._load(chat_id)
        status = await m.reply("⏳ Сканирование чата...")

        last_edit = 0
        i = 0

        try:
            async for msg in self.client.iter_messages(chat):
                i += 1
                try:
                    await self._process_message(msg, data)
                except Exception:
                    continue
                now = asyncio.get_event_loop().time()
                if now - last_edit > 3:
                    status = await self.safe_edit(status, f"🔍 Сканировано {i} сообщений...")
                    last_edit = now

            self._save(chat_id, data)
            await self.safe_edit(
                status,
                f"✅ Сканирование завершено.\nВсего сообщений: {data['messages_total']}\n"
                f"🖼 Изображений: {data['images']}\n🎞 GIF: {data['gifs']}\n"
                f"🎬 Видео: {data['videos']}\n📄 Файлы: {data['files']}"
            )
        finally:
            self.running[chat_id] = False

    async def cs_scancmd(self, m):
        chat = await m.get_chat()
        await self._scan_chat(m, chat)

    async def cs_infocmd(self, m):
        chat = await m.get_chat()
        data = self._load(chat.id)
        text = (
            f"📊 Общая статистика чата\n\n"
            f"Всего сообщений: <b>{data.get('messages_total',0)}</b>\n"
            f"🖼 Изображения: <b>{data.get('images',0)}</b>\n"
            f"🎞 GIF: <b>{data.get('gifs',0)}</b>\n"
            f"🎬 Видео: <b>{data.get('videos',0)}</b>\n"
            f"📄 Файлы: <b>{data.get('files',0)}</b>\n"
            f"🎙 Голосовые: <b>{data.get('voices',0)}</b>\n"
            f"🎥 Кружки: <b>{data.get('rounds',0)}</b>\n"
            f"Стикеры: <b>{data.get('stickers',0)}</b>"
        )
        await utils.answer(m, text)

    async def cs_usercmd(self, m):
        args = m.text.split(" ")
        if len(args) < 2:
            return await utils.answer(m, "❗ Укажи @username")

        username = args[1]
        chat = await m.get_chat()
        data = self._load(chat.id)

        try:
            user = await self.client.get_entity(username)
        except Exception:
            return await utils.answer(m, "❌ Пользователь не найден")

        uid = str(user.id)
        if uid not in data["users"]:
            return await utils.answer(m, "ℹ Нет сообщений от этого пользователя")

        udata = data["users"][uid]
        top_words = sorted(udata["words"].items(), key=lambda x: x[1], reverse=True)[:20]

        text = (
            f"📊 Статистика пользователя {username}\n"
            f"Всего сообщений: <b>{udata['messages']}</b>\n"
            f"🖼 Изображений: <b>{udata.get('images',0)}</b>\n"
            f"🎞 GIF: <b>{udata.get('gifs',0)}</b>\n"
            f"🎬 Видео: <b>{udata.get('videos',0)}</b>\n"
            f"📄 Файлы: <b>{udata.get('files',0)}</b>\n\n"
            f"🔝 Топ слов:\n" + ("\n".join([f"{w}: <b>{c}</b>" for w, c in top_words]) or "—")
        )
        await utils.answer(m, text)

    async def cs_clearcmd(self, m):
        chat = await m.get_chat()
        file = self.file_template.format(chat_id=chat.id)
        try:
            os.remove(file)
        except:
            pass
        await utils.answer(m, "🗑 Сохранение удалено")

    async def cs_twordscmd(self, m):
        chat = await m.get_chat()
        data = self._load(chat.id)

        if not data.get("words"):
            return await utils.answer(m, "ℹ Нет сообщений для анализа")

        top_words = sorted(data["words"].items(), key=lambda x: x[1], reverse=True)[:20]

        text = "📊 Общий топ слов в чате:\n"
        text += "\n".join([f"{w}: <b>{c}</b>" for w, c in top_words]) or "—"

        await utils.answer(m, text)