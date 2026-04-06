import asyncio
import asyncio
import re
import time
from dataclasses import dataclass

from telethon import events, functions, types, errors
from telethon.utils import get_peer_id
from .. import loader, utils

# meta developer: @Loranger_r

RESOURCE_TOKENS = [
    ("🕋", "миф"),
    ("☀️", "сф"),
    ("🎆", "п"),
    ("📦", "к"),
    ("🗳", "рк"),
    ("💎", "кр"),
    ("🔩", "скрап"),
    ("🌀", "Эсенция"),
    ("🎨", "палитра"),
    ("🌌", "зв"),
    ("📜", "эскиз"),
    ("💼", "псэ"),
    ("👜", "ссп"),
]

BOOST_LIGHTNING = ("⚡️", "⚡")
BOOST_TYPES = ["⛏️", "💰", "🔮", "📦"]
BOOST_TYPE_LABELS = {
    "⛏️": "руда",
    "💰": "деньги",
    "🔮": "плазма",
    "📦": "кейсы",
}
BOOST_LEVELS = ["⚪️", "🟢", "🔵", "🟣", "🟡", "🟠"]
BOOST_LEVEL_INDEX = {emoji: idx for idx, emoji in enumerate(BOOST_LEVELS)}
CHAIN_BOOST_PREFIX = "b:"
CHAIN_RESOURCE_PREFIX = "r:"


@dataclass
class ExpeditionCandidate:
    number: str
    reward_amount: int | None
    reward_token: str | None
    chance_text: str
    time_seconds: int | None
    level: int | None
    matched_token: str | None = None
    matched_rank: int | None = None
    boost_type: str | None = None
    boost_level: str | None = None
    extra_tokens: list[str] | None = None


@loader.tds
class MineExpeditions(loader.Module):
    """Автовыбор экспедиций MineEvo (приоритеты ресурсов, автосбор)."""

    strings = {"name": "MineExpeditions"}

    def __init__(self):
        self._client = None
        self._db = None
        self._mine_chat = None
        self._mine_chat_id = None
        self._log_chat = None
        self._log_chat_id = None
        self._lock = asyncio.Lock()
        self._task = None
        self._expedition_in_progress = False
        self._expedition_end_ts = None
        self._last_click_ts = 0.0
        self._refresh_until_ts = None
        self._next_query_ts = 0.0
        self._log_store: dict[str, dict[str, dict]] = {}

    async def client_ready(self, client, db):
        self._client = client
        self._db = db

        if self.get("enabled") is None:
            self.set("enabled", False)
        if self.get("priority_tokens") is None:
            self.set("priority_tokens", [])
        if self.get("time_pref") is None:
            self.set("time_pref", "shortest")
        if self.get("log_enabled") is None:
            self.set("log_enabled", True)
        if self.get("level_min") is None:
            self.set("level_min", None)
        if self.get("level_max") is None:
            self.set("level_max", None)
        if self.get("pref_scores") is None:
            self.set("pref_scores", {})

        self._mine_chat, _ = await utils.asset_channel(
            self._client,
            "MineExpeditions",
            "Группа для автоэкспедиций MineEvo",
            silent=True,
            archive=True,
            _folder="hikka",
        )
        self._mine_chat_id = get_peer_id(self._mine_chat)

        await self._invite_bot()
        await self._ensure_log_chat()

        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def _invite_bot(self):
        try:
            await self._client(functions.channels.InviteToChannelRequest(self._mine_chat, ["@mine_evo_bot"]))
        except Exception:
            pass
        try:
            await self._client(
                functions.channels.EditAdminRequest(
                    channel=self._mine_chat,
                    user_id="@mine_evo_bot",
                    admin_rights=types.ChatAdminRights(
                        post_messages=True,
                        edit_messages=True,
                        delete_messages=True,
                        ban_users=False,
                        invite_users=False,
                        change_info=False,
                        pin_messages=False,
                        add_admins=False,
                        manage_call=False,
                        anonymous=False,
                        manage_topics=False,
                    ),
                    rank="EVO",
                )
            )
        except Exception:
            pass

    async def _loop(self):
        while True:
            try:
                if self.get("enabled"):
                    await self._tick()
                await asyncio.sleep(1)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds + 5)
            except Exception:
                await asyncio.sleep(10)

    async def _tick(self):
        async with self._lock:
            now = time.time()
            if self._expedition_in_progress and self._expedition_end_ts:
                if now < self._expedition_end_ts:
                    return
                self._expedition_in_progress = False
                self._expedition_end_ts = None
            if self._refresh_until_ts and now < self._refresh_until_ts:
                return
            if now < self._next_query_ts:
                return

            await self._send_and_process_expedition()

    async def _send_and_process_expedition(self):
        self._next_query_ts = time.time() + 5
        msg = await self._send_and_wait("эксп", timeout=25)
        if not msg:
            return
        await self._drive_flow(msg)

    async def _drive_flow(self, msg, max_steps=8):
        steps = 0
        while msg and steps < max_steps:
            steps += 1
            acted = await self._process_message_once(msg)
            if not acted:
                return
            msg = await self._wait_for_next_message(timeout=25)

    async def _process_message_once(self, msg):
        text = msg.raw_text or ""

        if "Экспедиция завершена" in text and msg.buttons:
            btn = self._find_button(msg, "Забрать")
            if btn:
                try:
                    await btn.click()
                except Exception:
                    return False
                return True

        if "Текущая экспедиция" in text and "Возвращение через" in text:
            seconds = self._extract_time_seconds(text)
            if seconds:
                self._expedition_in_progress = True
                self._expedition_end_ts = time.time() + seconds
            return False

        if msg.buttons:
            btn = self._find_button(msg, "Отправиться")
            if btn:
                try:
                    await self._click_throttled(btn)
                except Exception:
                    return False
                return True
            btn = self._find_button(msg, "Выбрать")
            if btn:
                try:
                    await self._click_throttled(btn)
                except Exception:
                    return False
                return True

        return await self._process_expedition_list(msg)

    async def _process_expedition_list(self, msg):
        text = msg.raw_text or ""
        expeditions = self._parse_expeditions(text)
        try:
            self.log(
                "mexp parsed expeditions: %s",
                [
                    (e.number, e.level, e.reward_amount, e.reward_token, e.time_seconds, e.chance_text)
                    for e in expeditions
                ],
            )
        except Exception:
            pass
        if not expeditions:
            if self._apply_refresh_cooldown(text, msg):
                return
            return

        choice = self._choose_expedition(expeditions)
        try:
            self.log("mexp choice: %s", getattr(choice, "number", None))
        except Exception:
            pass
        if not choice:
            choice = expeditions[0]

        await self._log_expedition_choice(msg, expeditions, choice)

        if msg.buttons:
            wait_task = asyncio.create_task(self._wait_for_any_button(["Отправиться", "Выбрать"], timeout=25))
            clicked = await self._click_expedition_button(msg, choice.number)
            if not clicked:
                clicked = await self._send_expedition_number(choice.number)
            if not clicked:
                self._next_query_ts = time.time() + 5
                if not wait_task.done():
                    wait_task.cancel()
                self._next_query_ts = max(self._next_query_ts, time.time() + 20)
                return
            try:
                next_msg = await wait_task
            except Exception:
                next_msg = None
            if next_msg:
                btn = self._find_button(next_msg, "Отправиться")
                if not btn:
                    btn = self._find_button(next_msg, "Выбрать")
                if btn:
                    try:
                        await self._click_throttled(btn)
                    except Exception:
                        self._next_query_ts = time.time() + 5
                        return
            return

    async def _click_expedition_button(self, msg, expedition_number: str):
        if not msg.buttons:
            return False
        target_num = expedition_number
        if not target_num or not target_num.isdigit():
            target_num = ""
        candidates = []
        for row in msg.buttons:
            for button in row:
                text = (button.text or "").strip()
                if not text:
                    continue
                if "назад" in text.lower() or "отправ" in text.lower() or "выбрать" in text.lower():
                    continue
                normalized = text
                for keycap, digit in {
                    "1️⃣": "1",
                    "2️⃣": "2",
                    "3️⃣": "3",
                    "4️⃣": "4",
                    "5️⃣": "5",
                    "6️⃣": "6",
                    "7️⃣": "7",
                    "8️⃣": "8",
                    "9️⃣": "9",
                    "0️⃣": "0",
                }.items():
                    normalized = normalized.replace(keycap, digit)
                match = re.search(r"\d+", normalized)
                num = match.group(0) if match else None
                if num == expedition_number:
                    try:
                        await self._click_throttled(button)
                    except Exception:
                        return False
                    return True
                candidates.append((num, button))
        if target_num and candidates:
            try:
                idx = int(target_num) - 1
            except Exception:
                return False
            if 0 <= idx < len(candidates):
                try:
                    await self._click_throttled(candidates[idx][1])
                except Exception:
                    return False
                return True
        try:
            self.log(
                "mexp click failed for %s; buttons=%s",
                expedition_number,
                [[(b.text or "").strip() for b in row] for row in msg.buttons],
            )
        except Exception:
            pass
        return False

    async def _send_expedition_number(self, expedition_number):
        if not expedition_number or not str(expedition_number).isdigit():
            return False
        try:
            await self._client.send_message(self._work_chat_id, str(expedition_number))
            return True
        except Exception:
            return False

    def _apply_refresh_cooldown(self, text, msg):
        normalized = (text or "").replace(" : ", " ").replace(":", " ")
        if "Обновление" in normalized or "обнов" in normalized.lower():
            seconds = self._extract_time_seconds(normalized)
            if seconds:
                self._refresh_until_ts = time.time() + seconds
                self._next_query_ts = self._refresh_until_ts
                return True
        if msg and msg.buttons:
            for row in msg.buttons:
                for btn in row:
                    if "обнов" in (btn.text or "").lower():
                        fallback = 900
                        self._refresh_until_ts = time.time() + fallback
                        self._next_query_ts = self._refresh_until_ts
                        return True
        return False

    def _choose_expedition(self, expeditions):
        priority_tokens = self.get("priority_tokens") or []
        time_pref = self.get("time_pref") or "shortest"

        expeditions = self._filter_by_level(expeditions)
        if not expeditions:
            return None

        priority_choice = self._choose_by_priority_items(expeditions, time_pref, priority_tokens)
        if priority_choice:
            return priority_choice
        expeditions = self._apply_user_scores(expeditions)
        return self._choose_by_time(expeditions, time_pref)

    def _choose_by_priority_items(self, expeditions, time_pref, priority_items):
        if not priority_items:
            return None
        priority_items = self._normalize_priority_list(priority_items)
        for item in priority_items:
            if self._is_boost_item(item):
                boost_choice = self._choose_by_boost_item(expeditions, time_pref, item)
                if boost_choice:
                    return boost_choice
            else:
                resource_choice = self._choose_by_resource_item(expeditions, time_pref, item)
                if resource_choice:
                    return resource_choice
        return None

    def _choose_by_boost_item(self, expeditions, time_pref, item):
        token = self._chain_item_token(item)
        if not token:
            return None

        candidates = []
        for exp in expeditions:
            if exp.boost_type != token or not exp.boost_level:
                continue
            level_idx = BOOST_LEVEL_INDEX.get(exp.boost_level)
            if level_idx is None:
                continue
            candidates.append((-level_idx, exp))

        if not candidates:
            return None
        best_level = min(c[0] for c in candidates)
        best = [c[1] for c in candidates if c[0] == best_level]
        best = self._apply_user_scores(best)
        if len(best) > 1:
            max_reward = max((e.reward_amount or 0) for e in best)
            best = [e for e in best if (e.reward_amount or 0) == max_reward]
        return self._choose_by_time(best, time_pref)

    def _choose_by_resource_item(self, expeditions, time_pref, item):
        token = self._chain_item_token(item)
        if not token:
            return None
        matched = [e for e in expeditions if self._match_single_token(e.chance_text, token)]
        if not matched:
            return None
        matched = self._apply_user_scores(matched)
        if len(matched) > 1:
            max_reward = max((e.reward_amount or 0) for e in matched)
            matched = [e for e in matched if (e.reward_amount or 0) == max_reward]
        return self._choose_by_time(matched, time_pref)

    @staticmethod
    def _choose_by_time(candidates, time_pref):
        if not candidates:
            return None
        with_time = [c for c in candidates if c.time_seconds is not None]
        if not with_time:
            return candidates[0]
        if time_pref == "longest":
            return max(with_time, key=lambda c: c.time_seconds or 0)
        return min(with_time, key=lambda c: c.time_seconds or 0)

    @staticmethod
    def _match_single_token(chance_text, token):
        if not chance_text or not token:
            return False
        return token.lower() in chance_text.lower()

    def _parse_expeditions(self, text):
        cleaned = self._clean_text(text)
        lines = cleaned.splitlines()
        blocks = []
        current = []
        number_line_re = re.compile(r"^\s*(?:[^\d]*\s*)?(\d+)[\.\)]")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if number_line_re.match(line):
                if current:
                    blocks.append(current)
                current = [line]
                continue
            if current:
                current.append(line)

        if current:
            blocks.append(current)

        expeditions = []
        for block in blocks:
            number_match = number_line_re.match(block[0])
            if not number_match:
                continue
            number = number_match.group(1)
            reward_amount = None
            reward_token = None
            chance_text = ""
            time_seconds = None
            level = self._extract_level(block[0])
            boost_type = None
            boost_level = None
            extra_tokens = []
            for line in block:
                if "Награда" in line:
                    reward_amount = self._extract_reward(line)
                    if reward_token is None:
                        reward_token = self._extract_reward_token(line)
                if "Шанс найти" in line:
                    chance_text = line.split(":", 1)[-1].strip()
                if "Время" in line:
                    time_seconds = self._extract_time_seconds(line)
                if not boost_type or not boost_level:
                    parsed_type, parsed_level = self._extract_boost(line)
                    if parsed_type and parsed_level:
                        boost_type = parsed_type
                        boost_level = parsed_level
                if "доп" in line.lower():
                    if "💼" in line and "💼" not in extra_tokens:
                        extra_tokens.append("💼")
                    if "👜" in line and "👜" not in extra_tokens:
                        extra_tokens.append("👜")
            expeditions.append(
                ExpeditionCandidate(
                    number=number,
                    reward_amount=reward_amount,
                    reward_token=reward_token,
                    chance_text=chance_text,
                    time_seconds=time_seconds,
                    level=level,
                    boost_type=boost_type,
                    boost_level=boost_level,
                    extra_tokens=extra_tokens or None,
                )
            )
        return expeditions

    @staticmethod
    def _extract_reward(line):
        match = re.search(r"Награда\s*:\s*([\d\s,\.]+)", line)
        if not match:
            return None
        raw = re.sub(r"[^\d]", "", match.group(1))
        if not raw or not raw.isdigit():
            return None
        try:
            return int(raw)
        except Exception:
            return None

    @staticmethod
    def _extract_reward_token(line):
        if not line:
            return None
        emojis = re.findall(r"[\u2600-\u26FF\U0001F300-\U0001FAFF]", line)
        return emojis[0] if emojis else None

    @staticmethod
    def _extract_level(text):
        if not text:
            return None
        match = re.search(r"\b(\d+)\s*ур\.", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    @staticmethod
    def _extract_time_seconds(text):
        if not text:
            return None
        normalized = text.lower()
        normalized = normalized.replace("часов", "ч").replace("часа", "ч").replace("час", "ч")
        normalized = normalized.replace("минут", "мин").replace("минуты", "мин").replace("минута", "мин")
        normalized = normalized.replace("секунд", "сек").replace("секунды", "сек").replace("секунда", "сек")
        days = MineExpeditions._extract_unit(normalized, r"(\d+)\s*д\.?")
        hours = MineExpeditions._extract_unit(normalized, r"(\d+)\s*ч\.?")
        minutes = MineExpeditions._extract_unit(normalized, r"(\d+)\s*мин\.?")
        seconds = MineExpeditions._extract_unit(normalized, r"(\d+)\s*сек\.?")
        total = days * 86400 + hours * 3600 + minutes * 60 + seconds
        return total if total > 0 else None

    @staticmethod
    def _extract_unit(text, pattern):
        match = re.search(pattern, text)
        if not match:
            return 0
        try:
            return int(match.group(1))
        except Exception:
            return 0

    @staticmethod
    def _clean_text(text):
        if not text:
            return ""
        return re.sub(r"\*\*|__|`", "", text).strip()

    @staticmethod
    def _extract_boost(text):
        if not text:
            return None, None
        pattern = r"(?:⚡️|⚡)\s*([⛏️💰🔮📦])\s*([⚪️🟢🔵🟣🟡🟠])"
        match = re.search(pattern, text)
        if not match:
            return None, None
        return match.group(1), match.group(2)

    async def _send_and_wait(self, cmd, timeout):
        fut = asyncio.get_event_loop().create_future()

        async def handler(ev):
            if not fut.done():
                fut.set_result(ev.message)

        event_new = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        event_edit = events.MessageEdited(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        self._client.add_event_handler(handler, event_new)
        self._client.add_event_handler(handler, event_edit)
        try:
            await self._client.send_message(self._mine_chat_id, cmd)
        except Exception:
            self._client.remove_event_handler(handler, event_new)
            self._client.remove_event_handler(handler, event_edit)
            return None

        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            msg = None
        finally:
            self._client.remove_event_handler(handler, event_new)
            self._client.remove_event_handler(handler, event_edit)

        return msg

    async def _wait_for_next_message(self, timeout):
        fut = asyncio.get_event_loop().create_future()

        async def handler(ev):
            if not fut.done():
                fut.set_result(ev.message)

        event_new = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        event_edit = events.MessageEdited(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        self._client.add_event_handler(handler, event_new)
        self._client.add_event_handler(handler, event_edit)
        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            msg = None
        finally:
            self._client.remove_event_handler(handler, event_new)
            self._client.remove_event_handler(handler, event_edit)
        return msg

    async def _wait_for_button(self, contains, timeout):
        fut = asyncio.get_event_loop().create_future()
        target = contains.lower()

        async def handler(ev):
            msg = getattr(ev, "message", None)
            if not msg or not msg.buttons:
                return
            for row in msg.buttons:
                for btn in row:
                    if target in (btn.text or "").lower():
                        if not fut.done():
                            fut.set_result(msg)
                        return

        event_new = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        event_edit = events.MessageEdited(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        self._client.add_event_handler(handler, event_new)
        self._client.add_event_handler(handler, event_edit)
        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            msg = None
        finally:
            self._client.remove_event_handler(handler, event_new)
            self._client.remove_event_handler(handler, event_edit)
        return msg

    async def _wait_for_any_button(self, contains_list, timeout):
        if not contains_list:
            return None
        fut = asyncio.get_event_loop().create_future()
        targets = [c.lower() for c in contains_list]

        async def handler(ev):
            msg = getattr(ev, "message", None)
            if not msg or not msg.buttons:
                return
            for row in msg.buttons:
                for btn in row:
                    text = (btn.text or "").lower()
                    if any(t in text for t in targets):
                        if not fut.done():
                            fut.set_result(msg)
                        return

        event_new = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        event_edit = events.MessageEdited(incoming=True, chats=[self._mine_chat_id], from_users=[5522271758])
        self._client.add_event_handler(handler, event_new)
        self._client.add_event_handler(handler, event_edit)
        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            msg = None
        finally:
            self._client.remove_event_handler(handler, event_new)
            self._client.remove_event_handler(handler, event_edit)
        return msg

    async def _ensure_log_chat(self):
        if not self.get("log_enabled", True):
            return
        if self._log_chat_id:
            return
        try:
            self._log_chat, _ = await utils.asset_channel(
                self._client,
                "MineExpeditions Logs",
                "Логи автоэкспедиций MineEvo",
                silent=True,
                archive=True,
                _folder="hikka",
            )
            self._log_chat_id = get_peer_id(self._log_chat)
        except Exception:
            self._log_chat = None
            self._log_chat_id = None

    async def _log_expedition_choice(self, msg, expeditions, choice):
        if not self.get("log_enabled", True):
            return
        await self._ensure_log_chat()
        if not self._log_chat_id:
            return
        log_id = str(int(time.time() * 1000))
        store = {}
        for exp in expeditions:
            store[exp.number] = {
                "reward_token": exp.reward_token,
                "reward_amount": exp.reward_amount,
                "boost_type": exp.boost_type,
                "boost_level": exp.boost_level,
                "extra_tokens": exp.extra_tokens or [],
                "level": exp.level,
            }
        self._log_store[log_id] = store
        if len(self._log_store) > 50:
            for key in list(self._log_store.keys())[:10]:
                self._log_store.pop(key, None)

        text = (msg.raw_text or "").strip()
        if choice:
            text = f"{text}\n\n<b>Выбрано модулем:</b> {choice.number}"
        buttons = []
        row = []
        for exp in expeditions:
            row.append({"text": f"Выбрал бы {exp.number}", "callback": self._log_pick, "args": (log_id, exp.number)})
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        try:
            await self.inline.form(text=text, message=self._log_chat_id, reply_markup=buttons)
        except Exception:
            pass

    async def _log_pick(self, call, log_id, number):
        store = self._log_store.get(str(log_id), {})
        exp = store.get(str(number))
        if not exp:
            await call.answer("Данные не найдены.")
            return
        self._record_user_choice(exp)
        await call.answer("Записал предпочтение.")

    def _find_button(self, msg, contains):
        if not msg or not msg.buttons:
            return None
        target = contains.lower()
        for row in msg.buttons:
            for btn in row:
                if target in (btn.text or "").lower():
                    return btn
        return None

    @loader.command()
    async def mexpstart(self, message):
        """Запустить автоэкспедиции."""
        self.set("enabled", True)
        self._expedition_in_progress = False
        self._expedition_end_ts = None
        self._refresh_until_ts = None
        self._next_query_ts = 0.0
        await utils.answer(message, "<emoji document_id=5332533929020761310>✅</emoji> Экспедиции включены")
        await self._send_and_process_expedition()

    @loader.command()
    async def mexpstop(self, message):
        """Остановить автоэкспедиции."""
        self.set("enabled", False)
        await utils.answer(message, "<emoji document_id=5447644880824181073>⚠️</emoji> Экспедиции выключены")

    @loader.command()
    async def mexpstatus(self, message):
        """Статус экспедиций."""
        enabled = self.get("enabled")
        time_pref = self.get("time_pref") or "shortest"
        tokens = self._normalize_priority_list(self.get("priority_tokens") or [])
        lvl_min = self.get("level_min", None)
        lvl_max = self.get("level_max", None)
        log_enabled = self.get("log_enabled", True)
        lines = [
            f"<b>Экспедиции:</b> {'включены' if enabled else 'выключены'}",
            f"<b>Приоритеты:</b> {self._format_priority(tokens)}",
            f"<b>Уровни:</b> {self._format_level_range(lvl_min, lvl_max)}",
            f"<b>Время (если нет совпадений):</b> {'дольше' if time_pref == 'longest' else 'меньше'}",
            f"<b>Логи:</b> {'вкл' if log_enabled else 'выкл'}",
        ]
        if self._expedition_in_progress and self._expedition_end_ts:
            left = max(0, int(self._expedition_end_ts - time.time()))
            lines.append(f"<b>Активная экспедиция:</b> {left} сек.")
        await utils.answer(message, "\n".join(lines))

    @loader.command()
    async def mexpconfig(self, message):
        """Конфиг экспедиций."""
        await self.inline.form(
            text=self._build_menu_text("main"),
            message=message,
            reply_markup=self._build_menu_buttons("main"),
        )

    @loader.command()
    async def mexpguide(self, message):
        """Гайд по модулю."""
        text = "\n".join(
            [
                "<b>📘 Гайд MineExpeditions</b>",
                "",
                "1) <b>Приоритеты</b>",
                "Добавляй ресурсы и/или бусты в нужном порядке.",
                "Модуль идёт сверху вниз и выбирает первое подходящее.",
                "",
                "2) <b>Уровни экспедиций</b>",
                "Можно задать диапазон уровней (мин/макс).",
                "Если уровень вне диапазона — экспедиция игнорируется.",
                "",
                "3) <b>Логи и обучение</b>",
                "В отдельный чат пишутся все варианты и выбор модуля.",
                "Под логом есть кнопки «Выбрал бы N».",
                "Клики формируют предпочтения (ресурс, буст, уровень, доп. награда, размер награды).",
                "Дальше модуль пытается выбирать похожее.",
                "",
                "4) <b>Время</b>",
                "Если ничего из приоритетов не подошло — выбирает по времени (кор/дл).",
            ]
        )
        await utils.answer(message, text)

    def _build_menu_text(self, menu):
        tokens = self.get("priority_tokens") or []
        time_pref = self.get("time_pref") or "shortest"
        lvl_min = self.get("level_min", None)
        lvl_max = self.get("level_max", None)
        log_enabled = self.get("log_enabled", True)
        if menu == "priorities":
            return "\n".join(
                [
                    "<b>⭐ Приоритеты</b>",
                    "",
                    f"<b>Приоритеты:</b> {self._format_priority(tokens)}",
                    "",
                    "Нажми на ресурс или буст, чтобы добавить/убрать.",
                ]
            )
        if menu == "time":
            return "\n".join(
                [
                    "<b>⏳ Время</b>",
                    "",
                    f"<b>Если нет совпадений:</b> {'больше времени' if time_pref == 'longest' else 'меньше времени'}",
                ]
            )

        return "\n".join(
            [
                "<b>⚙️ Конфиг экспедиций</b>",
                "",
                f"<b>Приоритеты:</b> {self._format_priority(tokens)}",
                f"<b>Уровни:</b> {self._format_level_range(lvl_min, lvl_max)}",
                f"<b>Время (если нет совпадений):</b> {'дольше' if time_pref == 'longest' else 'меньше'}",
                f"<b>Логи:</b> {'вкл' if log_enabled else 'выкл'}",
                "",
                "Выбери раздел ниже.",
            ]
        )

    def _build_menu_buttons(self, menu):
        rows = []

        if menu == "priorities":
            tokens = self._normalize_priority_list(self.get("priority_tokens") or [])
            row = []
            for idx, (token, label) in enumerate(RESOURCE_TOKENS):
                key = self._priority_item_from_resource(token)
                is_on = key in tokens or token in tokens
                prefix = "✅ " if is_on else "➕ "
                row.append(
                    {
                        "text": f"{prefix}{token} {label}",
                        "callback": self._cfg_toggle_item,
                        "args": (key, "priorities"),
                    }
                )
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            row = []
            for token in BOOST_TYPES:
                key = self._priority_item_from_boost(token)
                label = BOOST_TYPE_LABELS.get(token, "буст")
                is_on = key in tokens
                prefix = "✅ " if is_on else "➕ "
                row.append(
                    {
                        "text": f"{prefix}⚡ {token} {label}",
                        "callback": self._cfg_toggle_item,
                        "args": (key, "priorities"),
                    }
                )
                if len(row) == 2:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append(
                [
                    {"text": "🧹 Очистить", "callback": self._cfg_clear, "args": ("priorities",)},
                    {"text": "⬅️ Назад", "callback": self._cfg_menu, "args": ("main",)},
                ]
            )
            return rows

        if menu == "time":
            rows.append([{"text": "⏳ Время: кор/дл", "callback": self._cfg_time, "args": ("time",)}])
            rows.append([{"text": "⬅️ Назад", "callback": self._cfg_menu, "args": ("main",)}])
            return rows

        rows.append(
            [
                {"text": "⭐ Приоритеты", "callback": self._cfg_menu, "args": ("priorities",)},
            ]
        )
        lvl_min = self.get("level_min", None)
        lvl_max = self.get("level_max", None)
        rows.append(
            [
                {"text": f"🎚 Мин: {lvl_min if lvl_min is not None else '-'}", "callback": self._cfg_level_min, "args": ("main",)},
                {"text": f"🎚 Макс: {lvl_max if lvl_max is not None else '-'}", "callback": self._cfg_level_max, "args": ("main",)},
            ]
        )
        rows.append([{"text": "⏳ Время", "callback": self._cfg_menu, "args": ("time",)}])
        rows.append([{"text": "📝 Логи: вкл/выкл", "callback": self._cfg_log_toggle, "args": ("main",)}])
        rows.append([{"text": "🔻 Закрыть", "action": "close"}])
        return rows

    async def _cfg_menu(self, call, menu):
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_toggle_item(self, call, item, menu):
        tokens = list(self.get("priority_tokens") or [])
        normalized = self._normalize_priority_item(item)
        if normalized in tokens:
            tokens.remove(normalized)
        else:
            tokens.append(normalized)
        tokens = self._normalize_priority_list(tokens)
        self.set("priority_tokens", tokens)
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_clear(self, call, menu):
        self.set("priority_tokens", [])
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_time(self, call, menu):
        current = self.get("time_pref") or "shortest"
        self.set("time_pref", "longest" if current == "shortest" else "shortest")
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_level_min(self, call, menu):
        current = self.get("level_min", None)
        next_val = self._cycle_level(current)
        self.set("level_min", next_val)
        self._ensure_level_bounds()
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_level_max(self, call, menu):
        current = self.get("level_max", None)
        next_val = self._cycle_level(current)
        self.set("level_max", next_val)
        self._ensure_level_bounds()
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    async def _cfg_log_toggle(self, call, menu):
        current = self.get("log_enabled", True)
        self.set("log_enabled", not current)
        await self._ensure_log_chat()
        await call.edit(text=self._build_menu_text(menu), reply_markup=self._build_menu_buttons(menu))

    def _format_priority(self, tokens):
        tokens = self._normalize_priority_list(tokens)
        if not tokens:
            return "не задано"
        parts = []
        for idx, item in enumerate(tokens, 1):
            parts.append(f"{idx}. {self._priority_item_label(item)}")
        return " | ".join(parts)

    def _priority_item_label(self, item):
        token = self._chain_item_token(item)
        if not token:
            return item
        if self._is_boost_item(item):
            label = BOOST_TYPE_LABELS.get(token, "буст")
            return f"⚡ {token} {label}"
        labels = {token: name for token, name in RESOURCE_TOKENS}
        label = labels.get(token, "")
        return f"{token} {label}".strip()

    @staticmethod
    def _priority_item_from_resource(token):
        return f"{CHAIN_RESOURCE_PREFIX}{token}"

    @staticmethod
    def _priority_item_from_boost(token):
        return f"{CHAIN_BOOST_PREFIX}{token}"

    @staticmethod
    def _is_boost_item(item):
        return item.startswith(CHAIN_BOOST_PREFIX)

    @staticmethod
    def _chain_item_token(item):
        if item.startswith(CHAIN_BOOST_PREFIX):
            return item[len(CHAIN_BOOST_PREFIX) :]
        if item.startswith(CHAIN_RESOURCE_PREFIX):
            return item[len(CHAIN_RESOURCE_PREFIX) :]
        return None

    def _normalize_priority_item(self, item):
        if not item:
            return item
        if item.startswith(CHAIN_BOOST_PREFIX) or item.startswith(CHAIN_RESOURCE_PREFIX):
            return item
        if item in BOOST_TYPES:
            return self._priority_item_from_boost(item)
        return self._priority_item_from_resource(item)

    def _normalize_priority_list(self, items):
        normalized = []
        for item in items or []:
            norm = self._normalize_priority_item(item)
            if norm and norm not in normalized:
                normalized.append(norm)
        return normalized

    def _format_level_range(self, lvl_min, lvl_max):
        if lvl_min is None and lvl_max is None:
            return "любой"
        if lvl_min is None:
            return f"до {lvl_max}"
        if lvl_max is None:
            return f"от {lvl_min}"
        return f"{lvl_min}-{lvl_max}"

    def _cycle_level(self, current):
        max_level = 5
        if current is None or current >= max_level:
            return 1
        if current < 1:
            return 1
        return current + 1

    def _ensure_level_bounds(self):
        lvl_min = self.get("level_min", None)
        lvl_max = self.get("level_max", None)
        if lvl_min is not None and lvl_max is not None and lvl_min > lvl_max:
            self.set("level_min", lvl_max)
            self.set("level_max", lvl_min)

    def _filter_by_level(self, expeditions):
        lvl_min = self.get("level_min", None)
        lvl_max = self.get("level_max", None)
        if lvl_min is None and lvl_max is None:
            return expeditions
        filtered = []
        for exp in expeditions:
            if exp.level is None:
                continue
            if lvl_min is not None and exp.level < lvl_min:
                continue
            if lvl_max is not None and exp.level > lvl_max:
                continue
            filtered.append(exp)
        return filtered or expeditions

    def _get_pref_scores(self):
        raw = self.get("pref_scores", {}) or {}
        if not isinstance(raw, dict):
            return {}
        return raw

    def _apply_user_scores(self, expeditions):
        scores = self._get_pref_scores()
        if not scores:
            return expeditions
        best_score = None
        best = []
        for exp in expeditions:
            score = self._score_expedition(exp, scores)
            if best_score is None or score > best_score:
                best_score = score
                best = [exp]
            elif score == best_score:
                best.append(exp)
        if best_score is None or best_score <= 0:
            return expeditions
        return best

    def _score_expedition(self, exp, scores):
        total = 0
        reward_scores = scores.get("reward", {})
        boost_scores = scores.get("boost", {})
        boost_level_scores = scores.get("boost_level", {})
        extra_scores = scores.get("extra", {})
        level_scores = scores.get("level", {})
        amount_scores = scores.get("amount", {})
        if exp.reward_token and exp.reward_token in reward_scores:
            total += reward_scores.get(exp.reward_token, 0)
        if exp.reward_amount is not None:
            bucket = str(min(int(exp.reward_amount // 1000), 1000))
            total += amount_scores.get(bucket, 0)
        if exp.boost_type and exp.boost_type in boost_scores:
            total += boost_scores.get(exp.boost_type, 0)
        if exp.boost_level and exp.boost_level in boost_level_scores:
            total += boost_level_scores.get(exp.boost_level, 0)
        if exp.extra_tokens:
            for token in exp.extra_tokens:
                total += extra_scores.get(token, 0)
        if exp.level is not None:
            total += level_scores.get(str(exp.level), 0)
        return total

    def _record_user_choice(self, exp):
        scores = self._get_pref_scores()
        reward_scores = scores.get("reward", {})
        boost_scores = scores.get("boost", {})
        boost_level_scores = scores.get("boost_level", {})
        extra_scores = scores.get("extra", {})
        level_scores = scores.get("level", {})
        amount_scores = scores.get("amount", {})
        if exp.get("reward_token"):
            token = exp["reward_token"]
            reward_scores[token] = reward_scores.get(token, 0) + 1
        amount = exp.get("reward_amount")
        if amount is not None:
            bucket = str(min(int(amount // 1000), 1000))
            amount_scores[bucket] = amount_scores.get(bucket, 0) + 1
        if exp.get("boost_type"):
            token = exp["boost_type"]
            boost_scores[token] = boost_scores.get(token, 0) + 1
        if exp.get("boost_level"):
            token = exp["boost_level"]
            boost_level_scores[token] = boost_level_scores.get(token, 0) + 1
        for token in exp.get("extra_tokens", []) or []:
            extra_scores[token] = extra_scores.get(token, 0) + 1
        level = exp.get("level")
        if level is not None:
            key = str(level)
            level_scores[key] = level_scores.get(key, 0) + 1
        scores["reward"] = reward_scores
        scores["boost"] = boost_scores
        scores["boost_level"] = boost_level_scores
        scores["extra"] = extra_scores
        scores["level"] = level_scores
        scores["amount"] = amount_scores
        self.set("pref_scores", scores)

    async def _click_throttled(self, button):
        now = time.monotonic()
        elapsed = now - self._last_click_ts
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        await button.click()
        self._last_click_ts = time.monotonic()
