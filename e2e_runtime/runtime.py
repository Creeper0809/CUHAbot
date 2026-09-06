from __future__ import annotations

import logging
import os
import re

import aiohttp
import discord
from aiohttp import web
from tortoise import Tortoise

from .api import create_app
from .manager import E2ERunManager
from .runner import DiscordSuiteRunner


logger = logging.getLogger(__name__)
TRIGGER_RE = re.compile(r"^!e2e_run ([0-9a-f-]{36}) (gateway|commands|components|gameflow|dungeon|semantics|roguelike|rewards|balance|farming|buildcraft|economy|visual|all) ([A-Za-z0-9_-]+)$")


class E2ERuntime:
    def __init__(self, bot, guild_id: int) -> None:
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = int(os.environ["E2E_CHANNEL_ID"])
        self.driver_bot_id = int(os.environ["MCP_BOT_ID"])
        self.driver_token = os.environ["MCP_TOKEN"]
        runner = DiscordSuiteRunner(bot, guild_id, self.channel_id)
        self.manager = E2ERunManager(
            self._dispatch,
            runner.execute,
            queue_size=int(os.getenv("E2E_QUEUE_SIZE", "10")),
            timeout_seconds=float(os.getenv("E2E_RUN_TIMEOUT_SECONDS", "900")),
        )
        self._runner: web.AppRunner | None = None
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        guild = self.bot.get_guild(self.guild_id)
        channel = self.bot.get_channel(self.channel_id)
        if not guild or not channel or getattr(channel, "guild", None) != guild:
            raise RuntimeError("configured E2E guild/channel is unavailable to the dev bot")
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            raise_for_status=False,
        )
        self.manager.start()
        app = create_app(self.manager, os.environ["E2E_API_TOKEN"], self.health)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(
            self._runner,
            os.getenv("E2E_API_BIND", "0.0.0.0"),
            int(os.getenv("E2E_API_PORT", "8765")),
        )
        await site.start()
        logger.info("E2E control plane started")

    async def close(self) -> None:
        await self.manager.stop()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        if self._session:
            await self._session.close()
            self._session = None

    async def _dispatch(self, run) -> None:
        assert self._session is not None
        url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
        headers = {"Authorization": f"Bot {self.driver_token}"}
        payload = {
            "content": f"!e2e_run {run.run_id} {run.suite} {run.nonce}",
            "allowed_mentions": {"parse": []},
        }
        async with self._session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                body = (await response.text())[:500]
                raise RuntimeError(f"Discord driver POST returned {response.status}: {body}")

    async def on_message(self, message: discord.Message) -> bool:
        if (
            not message.guild
            or message.guild.id != self.guild_id
            or message.channel.id != self.channel_id
            or not message.author.bot
            or message.author.id != self.driver_bot_id
        ):
            return False
        match = TRIGGER_RE.fullmatch(message.content)
        if not match:
            return False
        return await self.manager.accept_trigger(message, *match.groups())

    async def health(self) -> dict:
        db_ok = False
        try:
            connection = Tortoise.get_connection("default")
            await connection.execute_query("SELECT 1")
            db_ok = True
        except Exception:
            pass
        channel = self.bot.get_channel(self.channel_id)
        return {
            "status": "ok" if self.bot.is_ready() and db_ok and channel else "degraded",
            "bot_ready": self.bot.is_ready(),
            "database": db_ok,
            "guild_id": str(self.guild_id),
            "channel_id": str(self.channel_id),
            "channel_available": channel is not None,
            "queue_depth": self.manager._queue.qsize(),
        }
