# meta developer: @loranger_r

from .. import loader, utils
import random

@loader.tds
class D20(loader.Module):
    """Бросает 20-гранный кубик (d20)"""

    strings = {"name": "D20"}

    async def d20cmd(self, message):
        """Бросить d20"""
        roll = random.randint(1, 20)
        await utils.answer(message, f"🎲 Вы кинули D20. Вам выпало: <b>{roll}</b>")