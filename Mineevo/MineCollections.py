import asyncio
from telethon import events, functions, types, errors
from telethon.utils import get_peer_id
from .. import loader, utils

# meta developer: @Loranger_r

COLLECTIONS = [
    {
        "name": "Шахтёр I",
        "items": [
            {"name": "Костяные Останки", "start": "mine1"},
            {"name": "Черепок Горшка", "start": "mine7"},
            {"name": "Медная Монета", "start": "mine13"},
            {"name": "Осколок Кремня", "start": "mine19"},
            {"name": "Окаменевший Аммонит", "start": "mine24"},
        ],
    },
    {
        "name": "Шахтёр II",
        "items": [
            {"name": "Терракотовая Плитка", "start": "mine25"},
            {"name": "Старый Гвоздь", "start": "mine31"},
            {"name": "Деревянное Колесо", "start": "mine37"},
            {"name": "Ржавое Зубило", "start": "mine43"},
            {"name": "Расколотый Жёрнов", "start": "mine48"},
        ],
    },
    {
        "name": "Шахтёр III",
        "items": [
            {"name": "Свинцовая Пуля", "start": "mine49"},
            {"name": "Головка Кирки", "start": "mine55"},
            {"name": "Оловянный Солдатик", "start": "mine61"},
            {"name": "Медная Гильза", "start": "mine67"},
            {"name": "Обручальное Кольцо", "start": "mine72"},
        ],
    },
    {
        "name": "Шахтёр IV",
        "items": [
            {"name": "Рыболовное Грузило", "start": "mine73"},
            {"name": "Золотая Серьга", "start": "mine79"},
            {"name": "Подвеска", "start": "mine85"},
            {"name": "Керамический Осколок", "start": "mine91"},
            {"name": "Конденсатор", "start": "mine96"},
        ],
    },
    {
        "name": "Шахтёр V",
        "items": [
            {"name": "Кварцевая Линза", "start": "mine97"},
            {"name": "Осколок Вазы", "start": "mine103"},
            {"name": "Инклюз", "start": "mine109"},
            {"name": "Нефритовый Браслет", "start": "mine115"},
            {"name": "Топазовая Брошь", "start": "mine120"},
        ],
    },
    {
        "name": "Шахтёр VI",
        "items": [
            {"name": "Аметистовая Жеода", "start": "mine121"},
            {"name": "Часовой Механизм", "start": "mine127"},
            {"name": "Изумрудный Кристалл", "start": "mine133"},
            {"name": "Корона с Рубином", "start": "mine139"},
            {"name": "Алмазный Шлем", "start": "mine144"},
        ],
    },
    {
        "name": "Шахтёр VII",
        "items": [
            {"name": "Обогащенный Уран", "start": "mine145"},
            {"name": "Свинцовая Капсула", "start": "mine151"},
            {"name": "Радиоактивные Отходы", "start": "mine157"},
            {"name": "Топливный Стержень", "start": "mine163"},
            {"name": "Антирадин", "start": "mine168"},
        ],
    },
    {
        "name": "Шахтёр VIII",
        "items": [
            {"name": "Знак Опасности", "start": "mine169"},
            {"name": "Счётчик Гейгера", "start": "mine175"},
            {"name": "Каска Работника АЭС", "start": "mine181"},
            {"name": "Перчатка РЗК", "start": "mine187"},
            {"name": "Лопатка Турбины", "start": "mine192"},
        ],
    },
    {
        "name": "Шахтёр IX",
        "items": [
            {"name": "Раскалённый Осколок", "start": "mine193"},
            {"name": "Алмазная Пыль", "start": "mine199"},
            {"name": "Солнечная Панель", "start": "mine205"},
            {"name": "Повреждённая Рация", "start": "mine211"},
            {"name": "Обломок Антенны", "start": "mine216"},
        ],
    },
    {
        "name": "Шахтёр X",
        "items": [
            {"name": "Навигационный Чип", "start": "mine217"},
            {"name": "Лётные Данные", "start": "mine223"},
            {"name": "Растение", "start": "mine229"},
            {"name": "Иридиевый Слиток", "start": "mine235"},
            {"name": "Ракетный Двигатель", "start": "mine240"},
        ],
    },
    {
        "name": "Шахтёр XI",
        "items": [
            {"name": "Сгусток Материи", "start": "mine241"},
            {"name": "Алый Сгусток Материи", "start": "mine247"},
            {"name": "Изумрудный Сгусток Материи", "start": "mine253"},
            {"name": "Морозный Сгусток Материи", "start": "mine259"},
            {"name": "Теневой Сгусток Материи", "start": "mine264"},
        ],
    },
    {
        "name": "Шахтёр XII",
        "items": [
            {"name": "Палый Сгусток Материи", "start": "mine265"},
            {"name": "Мутный Сгусток Материи", "start": "mine271"},
            {"name": "Чистый Сгусток Материи", "start": "mine277"},
            {"name": "Хроматический Сгусток Материи", "start": "mine283"},
            {"name": "Сгусток Анти-Материи", "start": "mine288"},
        ],
    },
    {
        "name": "Шахтёр XIII",
        "items": [
            {"name": "Молекулярный Узел", "start": "mine289"},
            {"name": "Спокойный Электрон", "start": "mine295"},
            {"name": "Пульсирующий Протон", "start": "mine301"},
            {"name": "Волнистый Нейтрон", "start": "mine307"},
            {"name": "Нестабильное Ядро", "start": "mine312"},
        ],
    },
    {
        "name": "Шахтёр XIV",
        "items": [
            {"name": "Адронный Кластер", "start": "mine313"},
            {"name": "Тёмный Фотон", "start": "mine319"},
            {"name": "Глюонная Искра", "start": "mine325"},
            {"name": "Гравитонное Искривление", "start": "mine331"},
            {"name": "Ткань Мироздания", "start": "mine336"},
        ],
    },
]


@loader.tds
class MineCollections(loader.Module):
    """Автосбор коллекций MineEvo (переключение шахт по артефактам)."""

    strings = {"name": "MineCollections"}

    def __init__(self):
        self._client = None
        self._db = None
        self._mine_chat = None
        self._mine_chat_id = None
        self._lock = asyncio.Lock()
        self._task = None

    async def client_ready(self, client, db):
        self._client = client
        self._db = db

        if self.get("enabled") is None:
            self.set("enabled", False)
        if self.get("mode") is None:
            self.set("mode", "all")
        if self.get("col_idx") is None:
            self.set("col_idx", 0)
        if self.get("item_idx") is None:
            self.set("item_idx", 0)
        if self.get("interval") is None:
            self.set("interval", 60)

        self._mine_chat, _ = await utils.asset_channel(
            self._client,
            "MineCollections",
            "Группа для автосбора коллекций MineEvo",
            silent=True,
            archive=True,
            _folder="hikka",
        )
        self._mine_chat_id = get_peer_id(self._mine_chat)

        await self._invite_bot()

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

    def _current_target(self):
        mode = self.get("mode")
        col_idx = int(self.get("col_idx") or 0)
        item_idx = int(self.get("item_idx") or 0)

        if mode == "all":
            col = COLLECTIONS[col_idx % len(COLLECTIONS)]
            item = col["items"][item_idx % len(col["items"])]
            return col_idx % len(COLLECTIONS), item_idx % len(col["items"]), col, item

        try:
            col_number = int(mode)
            col_number = max(1, min(14, col_number))
        except Exception:
            col_number = 1

        col_idx = col_number - 1
        col = COLLECTIONS[col_idx]
        item = col["items"][item_idx % len(col["items"])]
        return col_idx, item_idx % len(col["items"]), col, item

    def _advance_target(self):
        mode = self.get("mode")
        col_idx = int(self.get("col_idx") or 0)
        item_idx = int(self.get("item_idx") or 0)

        if mode == "all":
            col = COLLECTIONS[col_idx % len(COLLECTIONS)]
            item_idx += 1
            if item_idx >= len(col["items"]):
                item_idx = 0
                col_idx = (col_idx + 1) % len(COLLECTIONS)
            self.set("col_idx", col_idx)
            self.set("item_idx", item_idx)
            return

        try:
            col_number = int(mode)
            col_number = max(1, min(14, col_number))
        except Exception:
            col_number = 1
        col_idx = col_number - 1
        col = COLLECTIONS[col_idx]
        item_idx = (item_idx + 1) % len(col["items"])
        self.set("col_idx", col_idx)
        self.set("item_idx", item_idx)

    def _text_has_target(self, text, target_name):
        if not text or not target_name:
            return False
        return target_name.lower() in text.lower()

    async def _loop(self):
        while True:
            try:
                if self.get("enabled"):
                    await self._tick()
                await asyncio.sleep(max(5, int(self.get("interval") or 60)))
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds + 5)
            except Exception:
                await asyncio.sleep(30)

    async def _tick(self):
        async with self._lock:
            msg, _ = await self._send_and_wait(
                "ш",
                timeout=20,
                keywords=["Ты копаешь", "Копание завершено", "Выбрана шахта"],
            )
            if not msg:
                return

            text = msg.raw_text or ""
            _, _, col, item = self._current_target()
            found = self._text_has_target(text, item["name"])

            if "Ты копаешь" in text:
                if found:
                    await self._stop_and_collect(msg)
                    self._advance_target()
                    await self._select_current_artifact()
                return

            if "Копание завершено" in text:
                await self._collect_if_possible(msg)
                if found:
                    self._advance_target()
                await self._select_current_artifact()
                return

            if "Выбрана шахта" in text:
                await self._start_mining_if_possible(msg)

    async def _stop_and_collect(self, msg):
        btn = self._find_button(msg, "остановить")
        if btn:
            try:
                await btn.click()
            except Exception:
                pass

        done = await self._wait_for_keywords(
            timeout=30,
            keywords=["Копание завершено", "Собери ресурсы"],
        )
        if done:
            await self._collect_if_possible(done)

    async def _collect_if_possible(self, msg):
        btn = self._find_button(msg, "Собрать")
        if btn:
            try:
                await btn.click()
            except Exception:
                pass
            await self._wait_for_keywords(timeout=20, keywords=["Ресурсы собраны"])

    async def _start_mining_if_possible(self, msg):
        btn = self._find_button(msg, "Добывать")
        if btn:
            try:
                await btn.click()
            except Exception:
                pass

    async def _select_current_artifact(self):
        _, _, col, item = self._current_target()
        try:
            await self._client.send_message(self._mine_chat_id, f"/start {item['start']}")
        except Exception:
            return
        msg = await self._wait_for_keywords(timeout=20, keywords=["Выбрана шахта", "Выбрана зона", "Шахта"])
        if msg:
            await self._start_mining_if_possible(msg)

    async def _send_and_wait(self, cmd, timeout, keywords):
        fut = asyncio.get_event_loop().create_future()

        async def handler(ev):
            m = ev.message
            if any(k in (m.raw_text or "") for k in keywords) and not fut.done():
                fut.set_result(m)

        event = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=5522271758)
        self._client.add_event_handler(handler, event)
        try:
            sent = await self._client.send_message(self._mine_chat_id, cmd)
        except Exception:
            self._client.remove_event_handler(handler, event)
            return None, None

        try:
            msg = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            msg = None
        finally:
            self._client.remove_event_handler(handler, event)

        return msg, sent

    async def _wait_for_keywords(self, timeout, keywords):
        fut = asyncio.get_event_loop().create_future()

        async def handler(ev):
            m = ev.message
            if any(k in (m.raw_text or "") for k in keywords) and not fut.done():
                fut.set_result(m)

        event_new = events.NewMessage(incoming=True, chats=[self._mine_chat_id], from_users=5522271758)
        event_edit = events.MessageEdited(incoming=True, chats=[self._mine_chat_id], from_users=5522271758)
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
    async def mcolstart(self, message):
        """Запустить автосбор."""
        self.set("enabled", True)
        await utils.answer(message, "<emoji document_id=5332533929020761310>✅</emoji> Автосбор включён")
        await self._select_current_artifact()

    @loader.command()
    async def mcolstop(self, message):
        """Остановить автосбор."""
        self.set("enabled", False)
        await utils.answer(message, "<emoji document_id=5447644880824181073>⚠️</emoji> Автосбор выключён")

    @loader.command()
    async def mcolmode(self, message):
        """Режим сбора: all или 1-14"""
        args = utils.get_args_raw(message).strip().lower()
        if not args:
            await utils.answer(message, "<b>Укажи режим: <code>all</code> или номер коллекции 1-14</b>")
            return
        if args == "all":
            self.set("mode", "all")
            await utils.answer(message, "<emoji document_id=5332533929020761310>✅</emoji> Режим: все коллекции")
            return
        try:
            num = int(args)
            if num < 1 or num > 14:
                raise ValueError
            self.set("mode", str(num))
            self.set("col_idx", num - 1)
            self.set("item_idx", 0)
            await utils.answer(message, f"<emoji document_id=5332533929020761310>✅</emoji> Режим: коллекция {num}")
        except Exception:
            await utils.answer(message, "<b>Неверный режим. Пример: <code>.mcolmode 3</code> или <code>.mcolmode all</code></b>")

    @loader.command()
    async def mcolstatus(self, message):
        """Статус автосбора."""
        enabled = self.get("enabled")
        mode = self.get("mode")
        col_idx, item_idx, col, item = self._current_target()
        await utils.answer(
            message,
            (
                f"<b>Автосбор:</b> {'включён' if enabled else 'выключен'}\n"
                f"<b>Режим:</b> {mode}\n"
                f"<b>Коллекция:</b> {col['name']}\n"
                f"<b>Текущий артефакт:</b> {item['name']} ({item['start']})\n"
                f"<b>Интервал проверки:</b> {self.get('interval')} сек."
            ),
        )

    @loader.command()
    async def mcolnext(self, message):
        """Перейти к следующему артефакту."""
        self._advance_target()
        _, _, col, item = self._current_target()
        await utils.answer(
            message,
            f"<emoji document_id=5332533929020761310>✅</emoji> Следующий артефакт: {item['name']} ({col['name']})",
        )
        if self.get("enabled"):
            await self._select_current_artifact()

    @loader.command()
    async def mcolint(self, message):
        """Интервал проверки в секундах."""
        args = utils.get_args_raw(message).strip()
        if not args:
            await utils.answer(message, f"<b>Текущий интервал:</b> <code>{self.get('interval')}</code> сек.")
            return
        try:
            val = int(args)
            if val < 10:
                val = 10
            self.set("interval", val)
            await utils.answer(message, f"<emoji document_id=5332533929020761310>✅</emoji> Интервал установлен: {val} сек.")
        except Exception:
            await utils.answer(message, "<b>Укажи число секунд, например <code>.mcolint 60</code></b>")
