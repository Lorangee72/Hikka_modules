# meta developer: @loranger_r
# meta name: GPTBridge
# meta desc: @ChatGPT_exclusive_bot

from .. import loader, utils
from telethon import functions
import asyncio

class GPTBridge(loader.Module):
    strings = {"name": "GPTBridge"}

    async def client_ready(self, client, db):
        self.client = client

    @loader.command()
    async def gpt(self, message):
        """Использование: .gpt вопрос"""
        question = utils.get_args_raw(message)
        if not question:
            return await message.edit("<b>❌ Вопрос не указан.</b>")

        chat = message.chat_id
        await message.delete()
        bot = "@ChatGPT_exclusive_bot"

        await self.client.send_message(bot, question)

        response = None
        previous_text = ""

        for _ in range(30):
            await asyncio.sleep(1)
            history = await self.client.get_messages(bot, limit=1)
            if not history:
                continue

            text = history[0].text or ""
            if text == previous_text or "Запрос отправлен" in text or text.strip() == "":
                continue

            previous_text = text
            response = text
            break

        if not response:
            await self.client.send_message(chat, "<b>❌ Бот не ответил за 30 секунд.</b>")
            return

        await self.client.send_message(chat, response)