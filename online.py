# meta developer: @loranger_r
# meta name: OnlineTracker
# meta desc: Трекер онлайна, с графиками, автоотчётами и аналитикой

from .. import loader, utils
from telethon import events
from telethon.tl.types import UpdateUserStatus, UserStatusOnline, UserStatusOffline
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import asyncio
import matplotlib.pyplot as plt

TZ = ZoneInfo("Europe/Moscow")
DB_KEY = "online_stats"
CFG_GROUP = "report_group_id"
MAX_MSG_LEN = 4000  # для телеграма


class OnlineTracker(loader.Module):
    strings = {"name": "OnlineTracker"}

    def __init__(self):
        self.current_online = None
        self.last_status = None
        self.report_task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.me = await client.get_me()

        if not self.db.get(self.strings["name"], DB_KEY):
            self.db.set(self.strings["name"], DB_KEY, {})

        self.client.add_event_handler(self._status_handler, events.Raw)
        self.report_task = asyncio.create_task(self._daily_report_loop())

    # ================= STATUS HANDLER =================
    async def _status_handler(self, event):
        if not isinstance(event, UpdateUserStatus):
            return
        if event.user_id != self.me.id:
            return

        now = datetime.now(TZ)
        day = now.strftime("%Y-%m-%d")
        stats = self.db.get(self.strings["name"], DB_KEY)
        stats.setdefault(day, {"sessions": [], "total": 0, "count": 0})

        # ===== ONLINE =====
        if isinstance(event.status, UserStatusOnline):
            if self.current_online is not None:
                return  # Уже в онлайне
            self.current_online = now
            self.last_status = "online"
            stats[day]["count"] += 1
            self.db.set(self.strings["name"], DB_KEY, stats)
            return

        # ===== OFFLINE =====
        if isinstance(event.status, UserStatusOffline):
            if self.current_online is None:
                return  # Оффлайн без начала сессии
            start = self.current_online
            end = now
            seconds = int((end - start).total_seconds())

            # проверяем последнюю сессию
            if stats[day]["sessions"]:
                last = stats[day]["sessions"][-1]
                last_start = datetime.strptime(last["from"], "%H:%M")
                last_end = datetime.strptime(last["to"], "%H:%M")

                # если накладывается — обновляем конец
                if start <= last_end:
                    last["to"] = end.strftime("%H:%M")
                    last["seconds"] = int((end - last_start).total_seconds())
                    stats[day]["total"] = sum(s["seconds"] for s in stats[day]["sessions"])
                    self.current_online = None
                    self.last_status = "offline"
                    self.db.set(self.strings["name"], DB_KEY, stats)
                    return

            # иначе создаём новую сессию
            stats[day]["sessions"].append({
                "from": start.strftime("%H:%M"),
                "to": end.strftime("%H:%M"),
                "seconds": seconds
            })
            stats[day]["total"] += seconds
            self.current_online = None
            self.last_status = "offline"
            self.db.set(self.strings["name"], DB_KEY, stats)

    # ================= COMMANDS =================
    @loader.command()
    async def online(self, message):
        """Статистика онлайна за день"""
        day = utils.get_args_raw(message) or datetime.now(TZ).strftime("%Y-%m-%d")
        stats = self.db.get(self.strings["name"], DB_KEY)
        data = stats.get(day)
        if not data:
            return await message.edit(f"❌ Нет данных за {day}")
        total = str(timedelta(seconds=data["total"]))
        count = data["count"]
        await message.edit(f"📊 Онлайн за {day}\n\n⏱ В онлайне: {total}\n🔁 Входов: {count}")

    @loader.command()
    async def onlinelog(self, message):
        """Все сессии за день (постранично)"""
        day = utils.get_args_raw(message) or datetime.now(TZ).strftime("%Y-%m-%d")
        stats = self.db.get(self.strings["name"], DB_KEY)
        data = stats.get(day)
        if not data or not data["sessions"]:
            return await message.edit(f"❌ Нет сессий за {day}")

        text = f"🧠 Сессии за {day}:\n\n"
        messages = []
        for i, s in enumerate(data["sessions"], 1):
            dur = str(timedelta(seconds=s["seconds"]))
            line = f"{i}. {s['from']} → {s['to']} ({dur})\n"
            if len(text) + len(line) > MAX_MSG_LEN:
                messages.append(text)
                text = ""
            text += line
        if text:
            messages.append(text)
        for msg in messages:
            await message.respond(msg)

    @loader.command()
    async def onlinegraph(self, message):
        """График онлайна за день"""
        day = utils.get_args_raw(message) or datetime.now(TZ).strftime("%Y-%m-%d")
        path = self._make_graph(day)
        if not path:
            return await message.edit("❌ Нет данных для графика")
        await message.respond(file=path)

    @loader.command()
    async def setonlinegroup(self, message):
        """Назначить группу для автоотчётов"""
        self.db.set(self.strings["name"], CFG_GROUP, message.chat_id)
        await message.edit("✅ Группа для автоотчётов установлена")

    @loader.command()
    async def onlineavg(self, message):
        """Средний онлайн, кол-во входов, активное время за период"""
        arg = utils.get_args_raw(message).lower() if utils.get_args_raw(message) else "week"
        now = datetime.now(TZ)

        if arg in ["week", "неделя"]:
            delta = timedelta(days=7)
        elif arg in ["2weeks", "2 недели"]:
            delta = timedelta(days=14)
        elif arg in ["month", "месяц"]:
            delta = timedelta(days=30)
        elif arg in ["3months", "3 месяца"]:
            delta = timedelta(days=90)
        elif arg in ["year", "год"]:
            delta = timedelta(days=365)
        else:
            return await message.edit("❌ Период не распознан. Используй: week, 2weeks, month, 3months, year")

        stats = self.db.get(self.strings["name"], DB_KEY)
        start_date = now - delta

        total_seconds = 0
        total_count = 0
        hour_count = [0]*24

        for day_str, day_data in stats.items():
            day_dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=TZ)
            if day_dt < start_date:
                continue
            total_seconds += day_data.get("total", 0)
            total_count += day_data.get("count", 0)
            for s in day_data.get("sessions", []):
                start_hour = int(s["from"].split(":")[0])
                hour_count[start_hour] += 1

        avg_online = str(timedelta(seconds=int(total_seconds/(delta.days)))) if total_seconds else "0:00:00"
        most_active_hour = hour_count.index(max(hour_count)) if max(hour_count) else None

        text = (
            f"📊 Аналитика за период: {arg}\n\n"
            f"⏱ Общее время в онлайне: {str(timedelta(seconds=total_seconds))}\n"
            f"🔁 Общее количество входов: {total_count}\n"
            f"🕒 Час, в который чаще всего онлайн: {most_active_hour}:00" if most_active_hour is not None else "Н/Д"
        )
        await message.edit(text)

    # ================= GRAPH =================
    def _make_graph(self, day):
        stats = self.db.get(self.strings["name"], DB_KEY)
        data = stats.get(day)
        if not data or not data["sessions"]:
            return None
        x, y = [], []
        for s in data["sessions"]:
            start = datetime.strptime(s["from"], "%H:%M")
            end = datetime.strptime(s["to"], "%H:%M")
            x.extend([start, end])
            y.extend([1, 0])
        plt.figure(figsize=(10, 3))
        plt.step(x, y, where="post")
        plt.title(f"Онлайн {day}")
        plt.yticks([])
        plt.tight_layout()
        path = f"/tmp/online_{day}.png"
        plt.savefig(path)
        plt.close()
        return path

    # ================= AUTO REPORT =================
    async def _daily_report_loop(self):
        while True:
            now = datetime.now(TZ)
            next_midnight = datetime.combine(now.date(), time(), tzinfo=TZ) + timedelta(days=1)
            await asyncio.sleep((next_midnight - now).total_seconds())

            group = self.db.get(self.strings["name"], CFG_GROUP)
            if not group:
                continue

            stats = self.db.get(self.strings["name"], DB_KEY)
            day = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
            data = stats.get(day)
            if not data:
                continue

            total = str(timedelta(seconds=data["total"]))
            count = data["count"]
            text = f"📊 Автоотчёт за {day}\n\n⏱ В онлайне: {total}\n🔁 Входов: {count}"
            graph = self._make_graph(day)
            await self.client.send_message(group, text, file=graph)