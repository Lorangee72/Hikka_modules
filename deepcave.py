# meta developer: @loranger_r

from .. import loader, utils
import asyncio
import re

@loader.tds
class DeepCaveMod(loader.Module):
    """DeepCave автофарм"""

    strings = {
        "name": "DeepCave"
    }

    def __init__(self):
        self.running = False
        self.waiting_mining = False

    async def get_last_msg(self):
        msgs = await self.client.get_messages("@DeepCaveGameBot", limit=1)
        return msgs[0] if msgs else None

    async def click(self, msg, text):
        for row in msg.buttons or []:
            for btn in row:
                if btn.text == text:
                    await btn.click()
                    return True
        return False

    def parse_time(self, text: str):
        """
        Ищет:
        Осталось: **X мин Y сек**
        """
        if not text:
            return None

        match = re.search(r"Осталось:\s*\*\*(?:(\d+)\s*мин\s*)?(?:(\d+)\s*сек)?\*\*", text)
        if not match:
            return None

        minutes = int(match.group(1) or 0)
        seconds = int(match.group(2) or 0)
        return minutes * 60 + seconds

    async def click_any_pickaxe(self, msg):
        SYSTEM = {
            "Завершить",
            "Начать добычу🪨⛏️",
            "🔽Спуститься в шахты⛏️"
        }

        for row in msg.buttons:
            for btn in row:
                if btn.text not in SYSTEM:
                    await btn.click()
                    return True
        return False

    async def deepcave_loop(self):
        while self.running:
            msg = await self.get_last_msg()

            if not msg:
                await asyncio.sleep(2)
                continue

            # Если идёт добыча — ждём по времени из текста
            mining_time = self.parse_time(msg.text or "")
            if mining_time:
                await asyncio.sleep(mining_time + 2)
                continue

            if msg.buttons:
                if await self.click(msg, "Завершить"):
                    await asyncio.sleep(2)
                    continue

                if await self.click(msg, "Начать добычу🪨⛏️"):
                    await asyncio.sleep(2)
                    continue

                if await self.click(msg, "🔽Спуститься в шахты⛏️"):
                    await asyncio.sleep(2)
                    continue

                if await self.click_any_pickaxe(msg):
                    await asyncio.sleep(1)
                    continue

            await asyncio.sleep(2)

    @loader.command()
    async def deepcaveon(self, message):
        if self.running:
            await utils.answer(message, "⛏️ Уже работает. Расслабься.")
            return

        self.running = True
        await utils.answer(
            message,
            "⛏️ DeepCave включён.\nЯ сам считаю время добычи. Без угадываний."
        )
        self.client.loop.create_task(self.deepcave_loop())

    @loader.command()
    async def deepcaveoff(self, message):
        self.running = False
        await utils.answer(message, "🛑 DeepCave остановлен.")