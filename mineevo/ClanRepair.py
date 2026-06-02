# -*- coding: utf-8 -*-
# meta developer: @Loranger_r

__version__ = (1, 0, 0)

import asyncio
import time

from hikka import loader, utils
from telethon import events, functions
from telethon.tl.functions.account import UpdateNotifySettingsRequest
from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

BOT_ID = 5522271758
INTERVAL = 3 * 3600

_NAV = {'»', '«', 'Назад', 'Добавить', 'Убрать',
        'Взять', 'Ремонт', 'Починить', 'Подписаться', 'Не подписываться'}


def _ts():
    return time.strftime("%H:%M:%S")


def _is_equip_btn(text: str) -> bool:
    t = (text or '').strip()
    if not t:
        return False
    for s in _NAV:
        if s in t:
            return False
    return True


@loader.tds
class ClanRepairModule(loader.Module):
    """Автопочинка клановой экипировки каждые 3 часа"""

    strings = {'name': 'ClanRepair'}

    def __init__(self):
        self._client = None
        self._lock = None
        self._chat = None
        self._peer = None
        self._task = None
        self._running = False
        self._logs = []

    async def client_ready(self, client, db):
        self._client = client
        self._lock = asyncio.Lock()
        await self._init_chat()

    def _log(self, msg):
        entry = f'[{_ts()}] {msg}'
        self._logs.append(entry)
        if len(self._logs) > 200:
            self._logs = self._logs[-150:]

    async def _init_chat(self):
        try:
            ch, _ = await utils.asset_channel(
                self._client,
                'ClanRepair',
                'Автопочинка клановой экипировки',
                silent=True,
                archive=True,
                _folder='hikka',
            )
            self._chat = ch.id
            self._peer = await self._client.get_input_entity(ch)
            self._log(f'Чат: {self._chat}')
            try:
                await self._client(UpdateNotifySettingsRequest(
                    peer=InputNotifyPeer(peer=self._peer),
                    settings=InputPeerNotifySettings(mute_until=2147483647),
                ))
            except Exception:
                pass
            try:
                await self._client(functions.channels.InviteToChannelRequest(ch, [BOT_ID]))
            except Exception:
                pass
        except Exception as e:
            self._log(f'Ошибка чата: {e}')

    async def _wait_new(self, check_fn, timeout=10.0):
        fut = self._client.loop.create_future()

        async def _h(ev):
            if fut.done():
                return
            if ev.sender_id != BOT_ID:
                return
            if check_fn(ev.message):
                fut.set_result(ev.message)

        self._client.add_event_handler(_h, events.NewMessage(chats=self._chat))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            try:
                self._client.remove_event_handler(_h)
            except Exception:
                pass

    async def _wait_edit(self, msg_id, timeout=6.0):
        fut = self._client.loop.create_future()

        async def _h(ev):
            if fut.done():
                return
            if ev.message.id == msg_id and ev.sender_id == BOT_ID:
                fut.set_result(ev.message)

        self._client.add_event_handler(_h, events.MessageEdited(chats=self._chat))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            try:
                self._client.remove_event_handler(_h)
            except Exception:
                pass

    async def _click_btn(self, msg, check_fn, timeout=5.0):
        if not msg or not msg.buttons:
            return None
        target = None
        for row in msg.buttons:
            for btn in row:
                if check_fn(btn.text):
                    target = btn
                    break
            if target:
                break
        if not target:
            return None
        self._log(f"  → '{target.text}'")
        edit_fut = asyncio.ensure_future(self._wait_edit(msg.id, timeout=timeout))
        try:
            await asyncio.wait_for(target.click(), timeout=2.0)
        except asyncio.TimeoutError:
            self._log('  Клик отправлен (ждём ответ...)')
        except Exception as e:
            self._log(f'  Ошибка клика: {e}')
            edit_fut.cancel()
            return None
        result = await edit_fut
        if result:
            return result
        try:
            msgs = await self._client.get_messages(self._peer, ids=[msg.id])
            return msgs[0] if msgs else None
        except Exception:
            return None

    async def _do_repair_cycle(self):
        if not self._peer:
            self._log('❌ Нет рабочего чата')
            return
        self._log('═══ Начинаю цикл ═══')
        await self._client.send_message(self._peer, 'клан')
        self._log("Отправил 'клан'")
        clan_msg = await self._wait_new(
            lambda m: m.buttons is not None,
            timeout=12.0,
        )
        if not clan_msg:
            self._log('❌ Нет ответа от бота')
            return
        new_equip_fut = asyncio.ensure_future(self._wait_new(
            lambda m: m.buttons is not None and (
                'Экипировка' in (m.text or '') or '🪖' in (m.text or '')
            ),
            timeout=12.0,
        ))
        equip_msg = await self._click_btn(
            clan_msg,
            lambda t: '🪖' in t and 'Экипировка' in t,
            timeout=8.0,
        )
        if equip_msg:
            new_equip_fut.cancel()
        else:
            equip_msg = await new_equip_fut
        if not equip_msg:
            try:
                recent = await self._client.get_messages(self._peer, limit=5)
                for m in recent:
                    if m.sender_id == BOT_ID and m.buttons and (
                        'Экипировка' in (m.text or '') or '🪖' in (m.text or '')
                    ):
                        equip_msg = m
                        self._log('✅ Меню найдено в истории чата')
                        break
            except Exception:
                pass
        if not equip_msg:
            self._log('❌ Меню экипировки не открылось')
            return
        self._log('✅ Меню экипировки получено')
        await self._repair_all(equip_msg)
        self._log('═══ Цикл завершён ═══')

    async def _repair_all(self, grid_msg):
        repaired = 0
        done = set()
        for _ in range(60):
            try:
                fresh = await self._client.get_messages(self._peer, ids=[grid_msg.id])
                if fresh and fresh[0]:
                    grid_msg = fresh[0]
            except Exception:
                pass
            if not grid_msg or not grid_msg.buttons:
                self._log('❌ Сетка пропала')
                break
            target_btn = None
            for row in grid_msg.buttons:
                for btn in row:
                    key = getattr(btn.button, 'data', btn.text)
                    if _is_equip_btn(btn.text) and key not in done:
                        target_btn = btn
                        break
                if target_btn:
                    break
            if not target_btn:
                self._log(f'✅ Все предметы обработаны, починено: {repaired}')
                break
            btn_key = getattr(target_btn.button, 'data', target_btn.text)
            done.add(btn_key)
            self._log(f"Предмет: '{target_btn.text}'")

            # Кликаем и проверяем алерт
            edit_fut = asyncio.ensure_future(self._wait_edit(grid_msg.id, timeout=6.0))
            answer = None
            try:
                answer = await asyncio.wait_for(target_btn.click(), timeout=2.0)
            except asyncio.TimeoutError:
                self._log('  Клик отправлен (ждём ответ...)')
            except Exception as e:
                self._log(f'  Ошибка клика: {e}')
                edit_fut.cancel()
                await asyncio.sleep(0.5)
                continue

            if answer and getattr(answer, 'alert', False):
                alert_text = getattr(answer, 'message', '') or ''
                if 'вернётся' in alert_text:
                    self._log('  ⏩ Занято — возвращаемся в сетку')
                    edited = await edit_fut
                    if edited:
                        back = await self._click_btn(
                            edited,
                            lambda t: 'Назад' in t or '«' in t,
                            timeout=5.0,
                        )
                        grid_msg = back or edited
                    await asyncio.sleep(0.3)
                    continue

            detail_msg = await edit_fut
            if not detail_msg:
                try:
                    fresh = await self._client.get_messages(self._peer, ids=[grid_msg.id])
                    detail_msg = fresh[0] if fresh else None
                except Exception:
                    pass
            if not detail_msg or not detail_msg.buttons:
                self._log('❌ Экран предмета не открылся — перезапуск')
                await asyncio.sleep(2.0)
                await self._do_repair_cycle()
                return
            await asyncio.sleep(0.3)
            repair_msg = await self._click_btn(
                detail_msg,
                lambda t: 'Ремонт' in t and 'Починить' not in t,
                timeout=6.0,
            )
            if not repair_msg or not repair_msg.buttons:
                self._log('❌ Нет кнопки Ремонт — жму Назад')
                grid_msg = await self._click_btn(
                    detail_msg,
                    lambda t: 'Назад' in t or '«' in t,
                    timeout=5.0,
                ) or grid_msg
                await asyncio.sleep(0.5)
                continue
            await asyncio.sleep(0.3)
            need_fix = False
            skip_fix = False
            for row in repair_msg.buttons:
                for btn in row:
                    if 'Починить' in btn.text:
                        need_fix = True
                        break
                    if 'требуется' in btn.text.lower():
                        skip_fix = True
                        break
                if need_fix or skip_fix:
                    break
            if need_fix:
                fixed_msg = await self._click_btn(
                    repair_msg,
                    lambda t: 'Починить' in t,
                    timeout=6.0,
                )
                repaired += 1
                self._log(f'  ✅ Починено ({repaired})')
                await asyncio.sleep(0.3)
                back_from = fixed_msg or repair_msg
            elif skip_fix:
                self._log('  ✓ Не требуется — скип')
                back_from = repair_msg
            else:
                self._log('  ⚠️ Неизвестное состояние — назад')
                back_from = repair_msg
            result = await self._click_btn(
                back_from,
                lambda t: 'Назад' in t or '«' in t,
                timeout=5.0,
            )
            if result:
                grid_msg = result
            else:
                self._log('⚠️ Назад не сработал')
            await asyncio.sleep(0.5)

    def _start_loop(self):
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            async with self._lock:
                try:
                    await self._do_repair_cycle()
                except Exception as e:
                    self._log(f'Ошибка: {e}')
            await asyncio.sleep(INTERVAL)

    def _stop_loop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    @loader.command()
    async def crstart(self, message):
        """Запустить авторемонт каждые 3ч"""
        if self._running:
            await utils.answer(message, '<b>⚙️ Уже запущен</b>')
            return
        if not self._chat:
            await utils.answer(message, '<b>❌ Чат не инициализирован — перезапусти модуль</b>')
            return
        self._start_loop()
        await utils.answer(message, '<b>✅ ClanRepair запущен (каждые 3ч)</b>')

    @loader.command()
    async def crstop(self, message):
        """Остановить авторемонт"""
        self._stop_loop()
        await utils.answer(message, '<b>🛑 ClanRepair остановлен</b>')

    @loader.command()
    async def crnow(self, message):
        """Запустить починку прямо сейчас"""
        if not self._chat:
            await utils.answer(message, '<b>❌ Чат не инициализирован</b>')
            return
        await utils.answer(message, '<b>🔧 Запускаю починку...</b>')
        async with self._lock:
            try:
                await self._do_repair_cycle()
            except Exception as e:
                self._log(f'Ошибка: {e}')
                await utils.answer(message, f'<b>❌ Ошибка: {e}</b>')
                return
        await utils.answer(message, '<b>✅ Починка завершена</b>')

    @loader.command()
    async def crlog(self, message):
        """Показать логи"""
        if not self._logs:
            await utils.answer(message, '<b>📋 Логи пусты</b>')
            return
        text = '\n'.join(self._logs[-60:])
        await utils.answer(message, f'<pre>{text}</pre>')

    @loader.command()
    async def crstat(self, message):
        """Статус модуля"""
        status = '✅ работает' if self._running else '❌ остановлен'
        chat = f'<code>{self._chat}</code>' if self._chat else '❌ нет'
        await utils.answer(message, f'<b>🛠 ClanRepair</b>\n\nСтатус: {status}\nЧат: {chat}')

    @loader.command()
    async def crchat(self, message):
        """Переинициализировать рабочий чат"""
        await utils.answer(message, '<b>🔄 Инициализирую чат...</b>')
        self._chat = None
        self._peer = None
        await self._init_chat()
        if self._chat:
            await utils.answer(message, f'<b>✅ Чат: <code>{self._chat}</code></b>')
        else:
            await utils.answer(message, '<b>❌ Не удалось создать чат</b>')
