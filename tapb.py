#meta developer: @loranger_r

from .. import loader, utils
import asyncio

@loader.tds
class InlineButtonAutoClickerMod(loader.Module):
    strings = {
        "name": "InlineButtonAutoClicker",
        "no_reply": "Ответь на сообщение с inline-кнопками и выполни команду.",
        "button_not_found": "Кнопка с текстом «{text}» не найдена.",
        "started": "Начал кликать по кнопке «{text}» каждые {interval}s, {count} раз.",
        "stopped": "Автоклик остановлен.",
    }

    def __init__(self):
        self.task = None
        self.stop_flag = False

    async def tapbcmd(self, message):
        args = utils.get_args(message)
        reply = await message.get_reply_message()
        if not reply:
            return await message.edit(self.strings("no_reply"))
        if len(args) < 3:
            return await message.edit("Использование: `.tapb <текст кнопки> <интервал_в_сек> <кол-во>`")

        try:
            interval = float(args[-2])
            count = int(args[-1])
        except:
            return await message.edit("Интервал и количество должны быть числами.")

        btn_text = " ".join(args[:-2])

        try:
            buttons = await reply.get_buttons()
        except:
            return await message.edit("Не удалось получить кнопки из сообщения.")

        target_btn = None
        for row in buttons:
            for b in row:
                if getattr(b, "text", None) == btn_text:
                    target_btn = b
                    break
            if target_btn:
                break

        if not target_btn:
            return await message.edit(self.strings("button_not_found").format(text=btn_text))

        self.stop_flag = False

        async def clicker():
            for i in range(count):
                if self.stop_flag:
                    break
                try:
                    await reply.click(text=btn_text)
                except Exception as e:
                    await message.client.send_message(message.to_id, f"Ошибка при клике: {e}")
                    break
                await asyncio.sleep(interval)

        self.task = asyncio.create_task(clicker())
        await message.edit(self.strings("started").format(text=btn_text, interval=interval, count=count))

    async def tapbstopcmd(self, message):
        self.stop_flag = True
        if self.task and not self.task.done():
            self.task.cancel()
        await message.edit(self.strings("stopped"))