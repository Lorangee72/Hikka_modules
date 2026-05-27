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

    async def client_ready(self, client, db):
        self.client = client

    async def _get_battle_msg(self):
        msgs = await self.client.get_messages(BOT_ID, limit=10)
        for msg in msgs:
            if not msg.buttons:
                continue
            for row in msg.buttons:
                for btn in row:
                    if btn.text in ("⚔️ Атаковать", "🔃 Обновить"):
                        return msg
        return None

    async def _click(self, msg, text):
        for row in msg.buttons or []:
            for btn in row:
                if btn.text == text:
                    await btn.click()
                    return True
        return False

    def _parse_hp_bars(self, text):
        """Возвращает количество полных █ в строке HP игрока."""
        if not text:
            return None
        match = re.search(r"💚[^\[]*\[([█░]+)\]", text)
        if not match:
            return None
        return match.group(1).count("█")

    async def _attack_loop(self):
        while self.running:
            try:
                msg = await self._get_battle_msg()

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
    async def autoattackon(self, message):
        """.autoattackon [секунды] — включить автоатаку"""
        args = utils.get_args_raw(message)
        if args:
            try:
                self.delay = float(args.strip())
            except ValueError:
                await utils.answer(message, "❌ Укажи задержку числом: .autoattackon 3.5")
                return

        if self.running:
            await utils.answer(message, "⚔️ Уже запущено.")
            return

        self.running = True
        await utils.answer(
            message,
            f"⚔️ <b>Автоатака запущена</b>\n"
            f"🤖 Бот: <code>{BOT_ID}</code>\n"
            f"⏱ Задержка: <code>{self.delay}с</code>\n"
            f"💔 При HP ≤ 1 полоски → 🔃 Обновить\n"
            f"💚 Когда HP > 1 полоски → ⚔️ Атаковать",
        )
        asyncio.ensure_future(self._attack_loop())

    @loader.command()
    async def autoattackoff(self, message):
        """.autoattackoff — остановить автоатаку"""
        self.running = False
        self.low_hp = False
        await utils.answer(message, "🛑 Автоатака остановлена.")

    @loader.command()
    async def autoattackstatus(self, message):
        """.autoattackstatus — текущий статус"""
        mode = "✅ Работает" if self.running else "🛑 Остановлена"
        hp = "⚠️ Низкий HP — жмёт 🔃 Обновить" if self.low_hp else "💪 Норма — жмёт ⚔️ Атаковать"
        await utils.answer(
            message,
            f"<b>AutoAttack статус:</b>\n"
            f"• Режим: {mode}\n"
            f"• HP: {hp}\n"
            f"• Задержка: <code>{self.delay}с</code>",
        )
