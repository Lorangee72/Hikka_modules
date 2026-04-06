# meta developer: @loranger_r

from .. import loader, utils

@loader.tds
class ChatFinderUniversal(loader.Module):
    """Универсальный поиск сообщений по ключевым словам"""

    strings = {
        "name": "ChatFinderUniversal",
        "no_args": "🤡 Ты забыл слово. `.fnd слово` или `.fndc слово`",
        "start_all": "🔍 Ищу **{}** во всех чатах…",
        "start_chat": "🔍 Ищу **{}** в этом чате…",
        "done": "✅ Готово. Найдено: {} сообщений",
        "nothing": "❌ Нихуя не найдено",
    }

    @loader.command()
    async def fnd(self, message):
        """Ищет слово во всех чатах"""
        await self._search(message, all_chats=True)

    @loader.command()
    async def fndc(self, message):
        """Ищет слово только в текущем чате"""
        await self._search(message, all_chats=False)

    async def _search(self, message, all_chats: bool):
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings["no_args"])
            return

        query = args.lower()
        if all_chats:
            await utils.answer(message, self.strings["start_all"].format(query))
        else:
            await utils.answer(message, self.strings["start_chat"].format(query))

        results = []

        if all_chats:
            dialogs = await self.client.get_dialogs()
            for dialog in dialogs:
                try:
                    async for msg in self.client.iter_messages(dialog.id, search=query, limit=5):
                        if not msg.text:
                            continue
                        link = self._get_link(dialog, msg)
                        if link:
                            results.append(link)
                except Exception:
                    continue
        else:
            async for msg in self.client.iter_messages(message.chat_id, search=query, limit=10):
                if not msg.text:
                    continue
                link = self._get_link(message.chat, msg)
                if link:
                    results.append(link)

        if not results:
            await utils.answer(message, self.strings["nothing"])
            return

        text = "🔗 **Найденные сообщения:**\n\n"
        for i, link in enumerate(results, 1):
            text += f"{i}. {link}\n"

        text += f"\n{self.strings['done'].format(len(results))}"
        await utils.answer(message, text)

    def _get_link(self, chat, msg):
        try:
            if chat.username:
                return f"https://t.me/{chat.username}/{msg.id}"
            else:
                chat_short_id = str(chat.id).replace("-100", "")
                return f"https://t.me/c/{chat_short_id}/{msg.id}"
        except Exception:
            return None