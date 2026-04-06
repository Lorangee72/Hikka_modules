#meta developer: @loranger_r
from .. import loader, utils
from telethon.tl.types import ReactionEmoji, ReactionCustomEmoji, MessageEntityCustomEmoji
import asyncio, json, os, re, io
from datetime import datetime, timedelta

@loader.tds
class MsgStatsMod(loader.Module):
    strings = {
        "name": "MsgStats",
        "ms_start_desc": "Запустить сканирование",
        "ms_stop_desc": "Остановить сканирование",
        "ms_resume_desc": "Продолжить сканирование",
        "ms_info_desc": "Показать общую статистику",
        "ms_clear_desc": "Удалить сохранение",
        "ms_export_desc": "Выгрузить файл статистики",
        "ms_topwords_desc": "Топ слов",
        "ms_topreactions_desc": "Топ реакций"
    }

    file = "ms_data.json"
    running = False

    def _default_data(self):
        return {
            "index": 0,
            "total_chats": 0,
            "messages_total": 0,
            "messages_year": 0,
            "messages_week": 0,
            "words": {},
            "reactions": {},
            "voices": 0,
            "rounds": 0,
            "stickers": 0,
            "images": 0,
            "videos": 0,
            "gifs": 0,
            "files": 0,
            "done": False
        }

    def _load(self):
        if not os.path.exists(self.file):
            return self._default_data()
        with open(self.file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    async def safe_edit(self, msg_obj, text):
        try:
            return await msg_obj.edit(text)
        except:
            try:
                return await self.client.send_message(msg_obj.chat_id, text)
            except:
                return msg_obj

    async def client_ready(self, client, db):
        self.client = client
        self.db = db

    async def _get_all_dialogs(self):
        dialogs = []
        async for d in self.client.iter_dialogs():
            dialogs.append(d)
        return dialogs

    async def _process_dialog(self, dialog, data, year_border, week_border):
        try:
            async for msg in self.client.iter_messages(dialog.id, from_user="me"):
                dt = msg.date.replace(tzinfo=None)
                data["messages_total"] += 1
                if dt > year_border:
                    data["messages_year"] += 1
                if dt > week_border:
                    data["messages_week"] += 1

                if getattr(msg, "message", None):
                    for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9']+", msg.message.lower()):
                        data["words"][w] = data["words"].get(w, 0) + 1

                if getattr(msg, "reactions", None):
                    for r in msg.reactions.results:
                        reaction = r.reaction
                        if isinstance(reaction, ReactionEmoji):
                            key = f"emoji:{reaction.emoticon}"
                        elif isinstance(reaction, ReactionCustomEmoji):
                            key = f"custom:{reaction.document_id}"
                        else:
                            continue
                        data["reactions"][key] = data["reactions"].get(key, 0) + r.count

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
                        else:
                            data["images"] += 1
                    elif mime.startswith("video/"):
                        data["videos"] += 1
                    else:
                        data["files"] += 1
        except:
            return

    async def _scan(self, m, resume=False):
        if self.running:
            return await utils.answer(m, "⚠ Уже выполняется")
        self.running = True
        data = self._load() if resume else self._default_data()
        if not resume:
            self._save(data)
        dialogs = await self._get_all_dialogs()
        total = len(dialogs)
        data["total_chats"] = total
        self._save(data)
        status = await m.reply("⏳ Сканирование...")
        year_border = datetime.now() - timedelta(days=365)
        week_border = datetime.now() - timedelta(days=7)
        last_edit = 0
        start = data.get("index", 0)
        for i in range(start, total):
            if not self.running:
                self._save(data)
                return await utils.answer(status, "⏸ Остановлено")
            dialog = dialogs[i]
            data["index"] = i
            title = dialog.name or str(dialog.id)
            now = asyncio.get_event_loop().time()
            if now - last_edit > 3:
                status = await self.safe_edit(status, f"🔍 {i+1}/{total} — {title}")
                last_edit = now
            try:
                task = asyncio.create_task(self._process_dialog(dialog, data, year_border, week_border))
                await asyncio.wait_for(task, timeout=60)
            except:
                pass
            if i % 5 == 0:
                self._save(data)
        data["done"] = True
        self._save(data)
        self.running = False
        await self.safe_edit(status, "✅ Сканирование завершено")

    async def ms_startcmd(self, m):
        await self._scan(m, resume=False)

    async def ms_resumecmd(self, m):
        await self._scan(m, resume=True)

    async def ms_stopcmd(self, m):
        if not self.running:
            return await utils.answer(m, "⚠ Не запущено")
        self.running = False
        await utils.answer(m, "⏸ Остановлено")

    async def ms_topreactionscmd(self, m):
        data = self._load()
        top = sorted(data.get("reactions", {}).items(), key=lambda x: x[1], reverse=True)[:30]
        text = "🔝 Топ реакций:\n"
        entities = []
        offset = len(text)

        for k, c in top:
            if k.startswith("emoji:"):
                em = k.split(":", 1)[1]
                line = f"{em}: <b>{c}</b>\n"
                text += line
                offset += len(line)
            elif k.startswith("custom:"):
                doc_id = int(k.split(":", 1)[1])
                text += "▫️"
                entities.append(
                    MessageEntityCustomEmoji(
                        offset=offset,
                        length=1,
                        document_id=doc_id
                    )
                )
                offset += 1
                line = f": <b>{c}</b>\n"
                text += line
                offset += len(line)

        await self.client.send_message(m.chat_id, text, entities=entities)

    async def ms_exportcmd(self, m):
        data = self._load()
        file = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode())
        file.name = "msgstats.json"
        await self.client.send_file(m.chat_id, file, caption="📁 Полная статистика сообщений")

    async def ms_clearcmd(self, m):
        try:
            os.remove(self.file)
        except:
            pass
        await utils.answer(m, "🗑 Сохранение удалено")