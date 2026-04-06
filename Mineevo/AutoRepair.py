# meta developer: @Loranger_r
__version__ = (1, 1, 3)

from .. import loader, utils
from telethon.tl.types import Message, ChatAdminRights
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon import events, functions, errors
import asyncio
import re
import time

@loader.tds
class NazomiAutoRepair(loader.Module):
    strings = {'name': 'AutoRepair'}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("auto_repair", True, 'Статус проверки прочности', validator=loader.validators.Boolean()),
            loader.ConfigValue(
                "min_durability",
                15,
                "Минимальная прочность (в %) для автопочинки",
                validator=loader.validators.Integer(minimum=1, maximum=100),
            ),
        )
        self.sleep_until = 0
        self.lock = None
        self.client = None
        self.work_channel = None
        self.boss_monitor_task_ref = None
        self.last_repair_by_chat = {}

    async def client_ready(self, client, db):
        self.client = client
        self.lock = asyncio.Lock()
        try:
            self.work_channel, _ = await utils.asset_channel(self.client, 'NazomiAutoRepair', 'Группа для работы NazomiAutoRepair', silent=True, archive=True, _folder='hikka')
            try:
                await self.client(functions.channels.InviteToChannelRequest(self.work_channel, [5522271758]))
                await self.client(functions.channels.EditAdminRequest(channel=self.work_channel, user_id=5522271758, admin_rights=ChatAdminRights(ban_users=False, post_messages=True, edit_messages=True), rank='EVO'))
            except Exception:
                self.work_channel = None
        except Exception:
            self.work_channel = None
                    
        try:
            await self.client(JoinChannelRequest('@Nazomi_Modules'))
        except:
            pass

        self.client.add_event_handler(self.battle_watch_handler, events.NewMessage(from_users=5522271758))
        self.client.add_event_handler(self.battle_watch_handler, events.MessageEdited(from_users=5522271758))

    def _extract_min_durability(self, text: str):
        if not text:
            return None
        percents = []
        try:
            for m in re.findall(r'(\d{1,3})\s*%', text):
                val = int(m)
                if 0 <= val <= 100:
                    percents.append(val)
        except Exception:
            pass
        try:
            for m in re.findall(r'прочност\w*[^0-9]{0,8}(\d{1,4})\s*/\s*(\d{1,4})', text, flags=re.IGNORECASE):
                cur = int(m[0])
                total = int(m[1])
                if total > 0:
                    percents.append(int(cur * 100 / total))
        except Exception:
            pass
        if not percents:
            return None
        return min(percents)

    def _extract_min_durability_from_buttons(self, message: Message):
        if not message or not getattr(message, "buttons", None):
            return None
        percents = []
        for row in message.buttons:
            for btn in row:
                btn_text = (btn.text or "").replace("\u00a0", " ")
                for m in re.findall(r"(\d{1,3})\s*%", btn_text):
                    try:
                        val = int(m)
                        if 0 <= val <= 100:
                            percents.append(val)
                    except Exception:
                        continue
        if not percents:
            return None
        return min(percents)

    def _is_low_durability(self, text: str, message: Message | None = None) -> bool:
        min_percent = self._extract_min_durability(text or "")
        if min_percent is None and message is not None:
            min_percent = self._extract_min_durability_from_buttons(message)
        if min_percent is None:
            return False
        threshold = int(self.config["min_durability"])
        return min_percent <= threshold

    def _extract_attack_percent(self, message: Message):
        if not message or not message.buttons:
            return None
        for row in message.buttons:
            for btn in row:
                btn_text = (btn.text or "").replace("\u00a0", " ")
                if "атак" not in btn_text.lower():
                    continue
                match = re.search(r"\((\d{1,3})\s*%?\)", btn_text) or re.search(r"(\d{1,3})\s*%", btn_text)
                if not match:
                    continue
                try:
                    val = int(match.group(1))
                    if 0 <= val <= 100:
                        return val
                except Exception:
                    return None
        return None

    async def battle_watch_handler(self, event: Message):
        if not self.config["auto_repair"] or time.time() < self.sleep_until:
            return
        msg = event.message if hasattr(event, "message") else event
        if not msg or not getattr(msg, "buttons", None):
            return
        percent = self._extract_attack_percent(msg)
        if percent is None:
            return
        threshold = int(self.config["min_durability"])
        if percent > threshold:
            return
        now = time.time()
        chat_id = msg.chat_id
        last_ts = self.last_repair_by_chat.get(chat_id, 0)
        if now - last_ts < 30:
            return
        self.last_repair_by_chat[chat_id] = now
        async with self.lock:
            await self.do_slots_repair(msg.peer_id)

    @loader.command()
    async def arstart(self, message: Message):
        self.config['auto_repair'] = True
        await utils.answer(message, '<b><emoji document_id=5462921117423384478>🛠</emoji> Проверка прочности включена</b>')

    @loader.command()
    async def arstop(self, message: Message):
        self.config['auto_repair'] = False
        await utils.answer(message, '<b><emoji document_id=5462990652943904884>😴</emoji> Проверка прочности выключена</b>')

    async def refresh_message(self, message: Message) -> Message:
        if not message:
            return None
        try:
            msgs = await self.client.get_messages(message.peer_id, ids=[message.id])
            return msgs[0] if msgs else message
        except Exception:
            return message

    async def boss_monitor_task(self, boss_msg: Message, peer_id):
        start_time = time.time()
        while time.time() - start_time < 900:
            await asyncio.sleep(5)
            msg = await self.refresh_message(boss_msg)
            if not msg or not msg.buttons:
                break
            percent = self._extract_attack_percent(msg)
            threshold = int(self.config["min_durability"])
            if percent is not None and percent <= threshold:
                await self.do_slots_repair(peer_id)
                await asyncio.sleep(5)

    async def do_slots_repair(self, peer_id):
        await self.client.send_message(peer_id, 'Экип')
        start_time = time.time()
        eq_msg = None
        while time.time() - start_time < 5:
            await asyncio.sleep(0.5)
            msgs = await self.client.get_messages(peer_id, limit=3)
            for m in msgs:
                if m and m.text and 'Экипировка' in m.text and getattr(m, 'sender_id', None) == 5522271758:
                    eq_msg = m
                    break
            if eq_msg:
                break
        
        if not eq_msg:
            return

        async def click_btn(msg_to_click, text_matches):
            msg_to_click = await self.refresh_message(msg_to_click)
            if not msg_to_click or not msg_to_click.buttons:
                return False
            for row in msg_to_click.buttons:
                for btn in row:
                    btn_text = btn.text.lower()
                    if any(t.lower() in btn_text for t in text_matches):
                        try:
                            await btn.click()
                            await asyncio.sleep(1)
                            return True
                        except:
                            pass
            return False

        if not await click_btn(eq_msg, ['Слоты']):
            return

        await asyncio.sleep(1)
        eq_msg = await self.refresh_message(eq_msg)
        if not self._is_low_durability(eq_msg.text or "", eq_msg):
            await click_btn(eq_msg, ['Назад', 'Закрыть'])
            return
        for _ in range(3):
            if await click_btn(eq_msg, ['Починить всё', 'починить']):
                break
            await asyncio.sleep(0.5)
        
        await asyncio.sleep(0.5)
        await click_btn(eq_msg, ['Назад', 'Закрыть'])
