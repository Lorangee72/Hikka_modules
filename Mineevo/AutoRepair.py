# meta developer: @Loranger_r
__version__ = (1, 1, 4)

from .. import loader, utils
from telethon.tl.types import Message, ChatAdminRights
from telethon.tl.functions.channels import InviteToChannelRequest, JoinChannelRequest
from telethon import events, functions, errors
import asyncio
import re
import time
from datetime import datetime

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
        self.last_repair_msg_by_chat = {}
        self.repair_in_progress = False

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
        self._rotate_plasma_periods()

    def _period_keys(self):
        now = datetime.now()
        iso = now.isocalendar()
        return (
            now.date().isoformat(),
            f"{iso.year}-W{iso.week:02d}",
            f"{now.year}-{now.month:02d}",
        )

    def _rotate_plasma_periods(self):
        day_key, week_key, month_key = self._period_keys()
        if self.get("plasma_day_key") != day_key:
            self.set("plasma_day_key", day_key)
            self.set("plasma_day", 0)
        if self.get("plasma_week_key") != week_key:
            self.set("plasma_week_key", week_key)
            self.set("plasma_week", 0)
        if self.get("plasma_month_key") != month_key:
            self.set("plasma_month_key", month_key)
            self.set("plasma_month", 0)
        if self.get("plasma_total") is None:
            self.set("plasma_total", 0)

    def _add_plasma_spent(self, amount: int):
        if amount <= 0:
            return
        self._rotate_plasma_periods()
        self.set("plasma_day", int(self.get("plasma_day", 0)) + amount)
        self.set("plasma_week", int(self.get("plasma_week", 0)) + amount)
        self.set("plasma_month", int(self.get("plasma_month", 0)) + amount)
        self.set("plasma_total", int(self.get("plasma_total", 0)) + amount)

    def _extract_plasma_spent(self, text: str | None):
        if not text:
            return None
        cleaned = (
            text.replace("\u00a0", " ")
            .replace("\u202f", " ")
            .replace("\u2009", " ")
        )
        for line in cleaned.splitlines():
            low = line.lower()
            if "плазм" not in low:
                continue
            match = re.search(
                r"потрачен\w*\s*[:：·•\-]?\s*([0-9][0-9\s,.'`_]*)",
                line,
                flags=re.IGNORECASE,
            )
            if not match:
                match = re.search(r"([0-9][0-9\s,.'`_]*)", line)
            if not match:
                continue
            value = re.sub(r"\D", "", match.group(1))
            if not value:
                continue
            try:
                return int(value)
            except Exception:
                continue
        return None

    def _extract_click_alert_text(self, click_result):
        if not click_result:
            return ""
        if isinstance(click_result, str):
            return click_result
        text = getattr(click_result, "message", None)
        if isinstance(text, str):
            return text
        for attr in ("text", "msg", "_message"):
            val = getattr(click_result, attr, None)
            if isinstance(val, str) and val.strip():
                return val
        try:
            if hasattr(click_result, "stringify"):
                raw = click_result.stringify()
                if isinstance(raw, str):
                    m = re.search(r"message='([^']+)'", raw)
                    if m and m.group(1):
                        return m.group(1)
        except Exception:
            pass
        try:
            raw = str(click_result)
            if isinstance(raw, str) and "message=" in raw:
                m = re.search(r"message='([^']+)'", raw)
                if m and m.group(1):
                    return m.group(1)
        except Exception:
            pass
        return ""

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
        now = time.time()
        chat_id = msg.chat_id
        msg_id = getattr(msg, "id", None)
        if msg_id is not None:
            last_msg_id, last_msg_ts = self.last_repair_msg_by_chat.get(chat_id, (None, 0))
            if last_msg_id == msg_id and now - last_msg_ts < 120:
                return
        percent = self._extract_attack_percent(msg)
        if percent is None:
            return
        threshold = int(self.config["min_durability"])
        if percent > threshold:
            return
        last_ts = self.last_repair_by_chat.get(chat_id, 0)
        if now - last_ts < 30:
            return
        self.last_repair_by_chat[chat_id] = now
        if msg_id is not None:
            self.last_repair_msg_by_chat[chat_id] = (msg_id, now)
        await self._run_repair_if_idle(msg.peer_id)

    async def _run_repair_if_idle(self, peer_id):
        if self.repair_in_progress:
            return
        self.repair_in_progress = True
        try:
            async with self.lock:
                await self.do_slots_repair(peer_id)
        finally:
            self.repair_in_progress = False

    @loader.command()
    async def arstart(self, message: Message):
        self.config['auto_repair'] = True
        await utils.answer(message, '<b><emoji document_id=5462921117423384478>🛠</emoji> Проверка прочности включена</b>')

    @loader.command()
    async def arstop(self, message: Message):
        self.config['auto_repair'] = False
        await utils.answer(message, '<b><emoji document_id=5462990652943904884>😴</emoji> Проверка прочности выключена</b>')

    @loader.command()
    async def arplasma(self, message: Message):
        """Показать статистику расхода плазмы"""
        self._rotate_plasma_periods()
        day = f"{int(self.get('plasma_day', 0)):,}"
        week = f"{int(self.get('plasma_week', 0)):,}"
        month = f"{int(self.get('plasma_month', 0)):,}"
        total = f"{int(self.get('plasma_total', 0)):,}"
        await utils.answer(
            message,
            (
                "<b>💠 Расход плазмы (AutoRepairNs)</b>\n\n"
                f"• За день: <code>{day}</code>\n"
                f"• За неделю: <code>{week}</code>\n"
                f"• За месяц: <code>{month}</code>\n"
                f"• За все время: <code>{total}</code>"
            ),
        )

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
                await self._run_repair_if_idle(peer_id)
                await asyncio.sleep(5)

    async def do_slots_repair(self, peer_id):
        equip_cmd_msg = None
        try:
            equip_cmd_msg = await self.client.send_message(peer_id, 'Экип')
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
                    return False, ""
                for row in msg_to_click.buttons:
                    for btn in row:
                        btn_text = btn.text.lower()
                        if any(t.lower() in btn_text for t in text_matches):
                            try:
                                click_result = await btn.click()
                                await asyncio.sleep(1)
                                return True, self._extract_click_alert_text(click_result)
                            except:
                                pass
                return False, ""

            opened_slots, _ = await click_btn(eq_msg, ['Слоты'])
            if not opened_slots:
                return

            await asyncio.sleep(1)
            eq_msg = await self.refresh_message(eq_msg)
            if not self._is_low_durability(eq_msg.text or "", eq_msg):
                await click_btn(eq_msg, ['Назад'])
                await asyncio.sleep(0.5)
                eq_msg = await self.refresh_message(eq_msg)
                await click_btn(eq_msg, ['Закрыть'])
                return

            repaired = False
            repair_alert_text = ""
            for _ in range(3):
                clicked, alert_text = await click_btn(eq_msg, ['Починить всё', 'починить'])
                if clicked:
                    repaired = True
                    repair_alert_text = alert_text or ""
                    break
                await asyncio.sleep(0.5)

            plasma_spent = None
            if repaired:
                await asyncio.sleep(0.8)
                plasma_spent = self._extract_plasma_spent(repair_alert_text)
                eq_msg = await self.refresh_message(eq_msg)
                if plasma_spent is None:
                    plasma_spent = self._extract_plasma_spent(eq_msg.text if eq_msg else "")
                if plasma_spent is None:
                    try:
                        recent = await self.client.get_messages(peer_id, limit=3)
                    except Exception:
                        recent = []
                    for m in recent:
                        if getattr(m, "sender_id", None) != 5522271758:
                            continue
                        plasma_spent = self._extract_plasma_spent(getattr(m, "text", "") or "")
                        if plasma_spent is not None:
                            break
                if plasma_spent is not None:
                    self._add_plasma_spent(plasma_spent)

            await asyncio.sleep(0.5)
            await click_btn(eq_msg, ['Назад'])
            await asyncio.sleep(0.5)
            eq_msg = await self.refresh_message(eq_msg)
            await click_btn(eq_msg, ['Закрыть'])
        finally:
            if equip_cmd_msg:
                try:
                    await equip_cmd_msg.delete()
                except Exception:
                    pass
