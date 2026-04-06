# meta developer: @loranger_r
# meta desc: Эпштейнит текст на X процентов

import random
from telethon import events
from .. import loader, utils


@loader.tds
class EPCensorMod(loader.Module):
    """Цензура текста на заданный процент"""

    strings = {"name": "EPCensor"}

    def censor(self, text: str, percent: int) -> str:
        if percent <= 0:
            return text
        if percent >= 100:
            return "█" * len(text)

        chars = list(text)
        total = len(chars)
        to_censor = int(total * percent / 100)

        indexes = list(range(total))
        random.shuffle(indexes)

        censored = 0
        for i in indexes:
            if chars[i] != " ":
                chars[i] = "█"
                censored += 1
            if censored >= to_censor:
                break

        return "".join(chars)

    @loader.command()
    async def ep(self, message):
        """
        .ep <текст> <1-100>
        Цензурит текст на указанный процент
        """

        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, "Ты вообще собирался что-то вводить? 🤡")
            return

        try:
            text, percent = args.rsplit(" ", 1)
            percent = int(percent)
        except Exception:
            await utils.answer(
                message,
                "Формат для особо одарённых:\n.ep текст 50"
            )
            return

        if percent < 1 or percent > 100:
            await utils.answer(message, "Процент от 1 до 100. Не 1488.")
            return

        result = self.censor(text, percent)
        await utils.answer(message, result)