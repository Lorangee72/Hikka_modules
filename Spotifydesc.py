# meta developer: @loranger_r

import asyncio
from .. import loader, utils
import logging

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    raise ImportError("Установите spotipy: pip install spotipy")

from telethon import functions

logger = logging.getLogger(__name__)


@loader.tds
class SpotifyDescMod(loader.Module):

    strings = {"name": "SpotifyDesc"}

    def __init__(self):
        self.running = False
        self.sp = None
        self.sp_oauth = None
        self.token_info = None
        self.last_track_id = None
        self.last_is_playing = None

        self.config = loader.ModuleConfig(
            loader.ConfigValue("client_id", "", "Spotify Client ID"),
            loader.ConfigValue("client_secret", "", "Spotify Client Secret"),
            loader.ConfigValue("redirect_uri", "http://127.0.0.1:8888/callback", "Redirect URI"),
            loader.ConfigValue("refresh_token", "", "Spotify Refresh Token"),
            loader.ConfigValue("prefix_text", "", "Текст перед музыкой в описании")
        )

    async def client_ready(self, client, db):
        self._client = client
        if all([self.config["client_id"], self.config["client_secret"], self.config["refresh_token"]]):
            await self._spotify_connect()
            self.running = True
            asyncio.create_task(self.loop_update())

    async def _spotify_connect(self):
        try:
            self.sp_oauth = SpotifyOAuth(
                client_id=self.config["client_id"],
                client_secret=self.config["client_secret"],
                redirect_uri=self.config["redirect_uri"],
                scope="user-read-playback-state"
            )
            self.token_info = self.sp_oauth.refresh_access_token(self.config["refresh_token"])
            self.sp = spotipy.Spotify(auth=self.token_info['access_token'])
        except Exception as e:
            logger.error(f"Ошибка Spotify: {e}")

    async def loop_update(self):
        while True:
            if self.running:
                try:
                    await self.update_track_bio()
                except Exception as e:
                    logger.error(f"SpotifyDesc: {e}")
            await asyncio.sleep(5)

    async def update_track_bio(self):
        if not self.sp:
            return

        try:
            self.token_info = self.sp_oauth.refresh_access_token(self.config["refresh_token"])
            self.sp = spotipy.Spotify(auth=self.token_info['access_token'])
        except:
            return

        current = self.sp.current_user_playing_track()

        if not current or not current.get("item"):
            track_id = None
            is_playing = False
        else:
            track_id = current["item"]["id"]
            is_playing = current.get("is_playing")

        if track_id == self.last_track_id and is_playing == self.last_is_playing:
            return

        self.last_track_id = track_id
        self.last_is_playing = is_playing

        prefix = self.config["prefix_text"].strip()
        prefix = (prefix + " ") if prefix else ""

        if not current or not current.get("item"):
            track_str = prefix + "⏸️ Музыка сейчас не играет"
        else:
            track = current["item"]
            artists = ", ".join(a["name"] for a in track["artists"])
            title = track["name"]
            status = "▶️" if is_playing else "⏸️"
            track_str = f"{prefix}{status} {artists} – {title}"

        me = await self._client.get_me()
        bio = getattr(me, "bio", "") or ""
        parts = [p.strip() for p in bio.split(" — ") if p.strip()]
        parts = [p for p in parts if not p.startswith(("▶️", "⏸️"))]
        parts.append(track_str)

        new_bio = " — ".join(parts)

        import re
        new_bio = re.sub(r"\s+", " ", new_bio).strip()

        await self._client(functions.account.UpdateProfileRequest(about=new_bio))

    @loader.command()
    async def spotify(self, message):
        if not self.sp:
            try:
                await self._spotify_connect()
            except:
                pass

        if not self.sp:
            await utils.answer(message, "❌ Spotify не настроен")
            return

        try:
            self.token_info = self.sp_oauth.refresh_access_token(self.config["refresh_token"])
            self.sp = spotipy.Spotify(auth=self.token_info['access_token'])
        except:
            await utils.answer(message, "❌ Ошибка доступа к Spotify")
            return

        current = self.sp.current_user_playing_track()

        if not current or not current.get("item"):
            await utils.answer(message, "⏸️ Музыка сейчас не играет")
            return

        track = current["item"]
        artists = ", ".join(a["name"] for a in track["artists"])
        title = track["name"]
        is_playing = current.get("is_playing", False)
        status = "▶️" if is_playing else "⏸️"

        progress_ms = current.get("progress_ms", 0)
        duration_ms = track.get("duration_ms", 1)
        progress_s = progress_ms // 1000
        duration_s = duration_ms // 1000

        def fmt(t):
            return f"{t//60:02d}:{t%60:02d}"

        bar_length = 20
        filled = int((progress_ms / duration_ms) * bar_length)
        bar = "▓" * filled + "░" * (bar_length - filled)

        text = (
            f"🎧 <b>Сейчас играет:</b>\n\n"
            f"{status} <b>{artists}</b> – <i>{title}</i>\n"
            f"{fmt(progress_s)} {bar} {fmt(duration_s)}"
        )

        await utils.answer(message, text)

    @loader.command()
    async def spotifyon(self, message):
        self.running = True
        await utils.answer(message, "✔ Автообновление Spotify включено")

    @loader.command()
    async def spotifyoff(self, message):
        self.running = False
        await utils.answer(message, "❌ Автообновление Spotify выключено")