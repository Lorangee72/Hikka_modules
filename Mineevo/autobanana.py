# meta developer: @Loranger_r
import asyncio
import re
import time
from .. import loader


@loader.tds
class AutoBanana(loader.Module):
    """Авто сбор бананов с бананового дерева."""

    strings = {"name": "AutoBanana"}

    def __init__(self):
        self.sender_id = 5522271758
        self.client = None
        self.db = None
        self._task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        next_ts = self.db.get("AutoBanana", "next_run_ts", 0) or 0
        now = time.time()
        if next_ts > now:
            self._schedule_at(next_ts)
        else:
            asyncio.create_task(self._send_once())

    def _is_banana_success(self, text: str) -> bool:
        if not text:
            return False
        low = text.lower()
        return "ты сорвал" in low and "банан" in low and "бананового дерева" in low

    def _parse_cooldown(self, text: str) -> int | None:
        if not text:
            return None
        low = text.replace("\u00a0", " ")
        if "попробуй через" not in low:
            return None
        if "банан" not in low and "🍌" not in text:
            return None
        def _find(pattern: str) -> int:
            m = re.search(pattern, low, flags=re.IGNORECASE)
            return int(m.group(1)) if m else 0
        days = _find(r"(\d+)\s*д\.")
        hours = _find(r"(\d+)\s*ч\.")
        minutes = _find(r"(\d+)\s*м(?:ин)?\.?")
        seconds = _find(r"(\d+)\s*с\.")
        total = days * 86400 + hours * 3600 + minutes * 60 + seconds
        return total if total > 0 else None

    async def _send_once(self):
        try:
            await self.client.send_message(self.sender_id, "сорвать бананы")
        except Exception:
            pass

    def _schedule_at(self, ts: float):
        if self._task:
            self._task.cancel()

        async def runner():
            while True:
                now = time.time()
                if now >= ts:
                    break
                await asyncio.sleep(min(5, ts - now))
            await self._send_once()

        self._task = asyncio.create_task(runner())

    async def watcher(self, m):
        if not hasattr(m, "sender_id") or m.sender_id != self.sender_id:
            return
        text = m.text or ""
        if self._is_banana_success(text):
            await self._send_once()
            return
        cooldown = self._parse_cooldown(text)
        if cooldown:
            next_ts = time.time() + cooldown
            self.db.set("AutoBanana", "next_run_ts", next_ts)
            self._schedule_at(next_ts)
