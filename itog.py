# meta developer: @loranger_r

from .. import loader, utils
from datetime import datetime, timezone
from telethon.tl.functions.messages import ImportChatInviteRequest
import re

@loader.tds
class ItogChannelMod(loader.Module):
    """Итоги канала (public + private)"""

    strings = {"name": "ItogChannel"}

    async def itogcmd(self, message):
        """
        .itog @channel
        .itog t.me/xxxxxx
        .itog @channel year
        .itog t.me/xxxxxx year 2025
        """
        args = utils.get_args(message)
        if not args:
            await message.edit("❌ Канал укажи. Я не экстрасенс.")
            return

        target = args[0]
        year = None
        now = datetime.now(timezone.utc)

        if len(args) >= 2 and args[1] == "year":
            year = int(args[2]) if len(args) >= 3 else now.year

        await message.edit("⏳ Думаю. Считаю циферки.")

        entity = None

        invite_match = re.search(r"(?:t\.me/|\+)([A-Za-z0-9_-]+)", target)
        if invite_match and not target.startswith("@"):
            invite_hash = invite_match.group(1)
            try:
                await self.client(ImportChatInviteRequest(invite_hash))
            except:
                pass

            try:
                entity = await self.client.get_entity(target)
            except Exception as e:
                await message.edit(f"❌ Не могу получить доступ к каналу.\n{e}")
                return
        else:
            try:
                entity = await self.client.get_entity(target)
            except Exception as e:
                await message.edit(f"❌ Канал не найден.\n{e}")
                return

        total_posts = 0
        total_views = 0
        total_reactions = 0
        total_comments = 0

        top_views = 0
        top_msg = None

        async for msg in self.client.iter_messages(entity):
            if not msg.date:
                continue

            msg_year = msg.date.year

            if year:
                if msg_year < year:
                    break
                if msg_year > year:
                    continue

            total_posts += 1

            views = msg.views or 0
            total_views += views

            if views > top_views:
                top_views = views
                top_msg = msg

            if msg.reactions:
                total_reactions += sum(r.count for r in msg.reactions.results)

            if msg.replies:
                total_comments += msg.replies.replies or 0

        avg_views = total_views // total_posts if total_posts else 0

        title = f"ЗА {year}" if year else "ЗА ВСЁ ВРЕМЯ"

        text = (
            f"📊 ИТОГИ {title}\n\n"
            f"📌 Канал: {target}\n"
            f"📝 Постов: {total_posts}\n"
            f"👀 Просмотров: {total_views}\n"
            f"📈 Среднее: {avg_views}\n"
            f"❤️ Реакций: {total_reactions}\n"
            f"💬 Комментариев: {total_comments}\n"
        )

        if top_msg:
            try:
                link = f"https://t.me/c/{entity.id}/{top_msg.id}"
            except:
                link = "ссылка недоступна"
            text += f"\n🏆 Топ-пост: {top_views} просмотров\n🔗 {link}"

        await message.edit(text)