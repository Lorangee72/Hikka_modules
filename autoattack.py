# meta developer: @loranger_r

from .. import loader, utils
import asyncio
import re

BOT_ID = 8666345479


@loader.tds
class AutoAttackMod(loader.Module):
    """Автоатака игрового бота с защитой по HP"""

    strings = {"name": "AutoAttack"}

    def __init__(self):
        self.running = False
        self.delay = 5.0
        self.low_hp = False
        self._cached_msg_id = None

    async def client_ready(self, client, db):
        self.client = client

    async def _find_battle_msg(self):
        """Ищет боевое сообщение среди последних 10."""
        msgs = await self.client.get_messages(BOT_ID, limit=10)
        for msg in msgs:
            if not msg.buttons:
                continue
            for row in msg.buttons:
                for btn in row:
                    if btn.text in ("⚔️ Атаковать", "🔃 Обновить"):
                        return msg
        return None

    async def _get_msg(self):
        """Возвращает закешированное сообщение (обновляет его из истории)."""
        if self._cached_msg_id:
            msgs = await self.client.get_messages(BOT_ID, ids=[self._cached_msg_id])
            msg = msgs[0] if msgs else None
            if msg and msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if btn.text in ("⚔️ Атаковать", "🔃 Обновить"):
                            return msg
        # Кеш устарел — ищем заново
        msg = await self._find_battle_msg()
        if msg:
            self._cached_msg_id = msg.id
        return msg

    async def _click(self, msg, text):
        for row in msg.buttons or []:
            for btn in row:
                if btn.text == text:
                    await btn.click()
                    return True
        return False

    def _parse_hp_bars(self, text):
        if not text:
            return None
        match = re.search(r"💚[^\[]*\[([█░]+)\]", text)
        if not match:
            return None
        return match.group(1).count("█")

    async def _attack_loop(self):
        while self.running:
            try:
                msg = await self._get_msg()

                if not msg:
                    await asyncio.sleep(self.delay)
                    continue

                hp_bars = self._parse_hp_bars(msg.raw_text or msg.text or "")

                if hp_bars is not None and hp_bars <= 1:
                    self.low_hp = True
                    await self._click(msg, "🔃 Обновить")
                else:
                    self.low_hp = False
                    if not await self._click(msg, "⚔️ Атаковать"):
                        await self._click(msg, "🔃 Обновить")

            except Exception:
                pass

            await asyncio.sleep(self.delay)

    @loader.command()
    async def aaon(self, message):
        """[секунды] — включить автоатаку"""
        args = utils.get_args_raw(message)
        if args:
            try:
                self.delay = float(args.strip())
            except ValueError:
                await utils.answer(message, "❌ Укажи задержку числом: .aaon 3.5")
                return

        if self.running:
            await utils.answer(message, "⚔️ Уже запущено.")
            return

        self.running = True
        self._cached_msg_id = None
        await utils.answer(message, f"⚔️ DM атака запущена | задержка {self.delay}с")
        asyncio.ensure_future(self._attack_loop())

    @loader.command()
    async def aaoff(self, message):
        """Остановить автоатаку"""
        self.running = False
        self.low_hp = False
        self._cached_msg_id = None
        await utils.answer(message, "🛑 Автоатака остановлена.")

    @loader.command()
    async def aas(self, message):
        """Текущий статус"""
        mode = "✅ Работает" if self.running else "🛑 Остановлена"
        hp = "⚠️ Низкий HP — жмёт 🔃 Обновить" if self.low_hp else "💪 Норма — жмёт ⚔️ Атаковать"
        await utils.answer(
            message,
            f"<b>AutoAttack:</b>\n"
            f"• {mode}\n"
            f"• {hp}\n"
            f"• Задержка: <code>{self.delay}с</code>",
        )
