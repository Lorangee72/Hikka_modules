#meta developer: @loranger_r

from .. import loader, utils


@loader.tds
class InlineButtonsExporterMod(loader.Module):
    strings = {
        "name": "InlineButtonsExporter",
        "no_reply": "Ответь на сообщение с *inline*-кнопками и выполни .ub",
        "no_buttons": "Inline-кнопок не найдено.",
        "done": "Найдено {count} inline-кнопок:",
    }

    async def ubcmd(self, message):
        reply = await message.get_reply_message()
        if not reply:
            return await message.edit(self.strings("no_reply"))

        try:
            btns = await reply.get_buttons()
        except:
            btns = None

        texts = []
        if btns:
            for row in btns:
                for b in row:
                    t = getattr(b, "text", None)
                    if t:
                        texts.append(t)

        if not texts:
            return await message.edit(self.strings("no_buttons"))

        header = self.strings("done").format(count=len(texts))
        body = "\n".join(texts)

        await message.delete()
        await message.client.send_message(message.to_id, f"{header}\n\n`{body}`")