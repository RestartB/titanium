import datetime
import logging
import traceback
from typing import TYPE_CHECKING

import aiohttp
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from main import TitaniumBot


class UptimeKuma(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

        try:
            self.uptime_kuma_server = bot.options["uptime-kuma-push"]

            if self.uptime_kuma_server is not None and self.uptime_kuma_server != "":
                logging.info(
                    f"[KUMA] Starting Uptime Kuma pinger (server: {bot.options['uptime-kuma-push']})..."
                )
                self.kuma_ping.start()
            else:
                logging.info(
                    "[KUMA] Disabling the Uptime Kuma pinger, no Uptime Kuma server was specified."
                )
                self.uptime_kuma_server = None
        except KeyError:
            logging.info(
                "[KUMA] Disabling the Uptime Kuma pinger, no Uptime Kuma server was specified."
            )
            self.uptime_kuma_server = None

    def cog_unload(self):
        if self.uptime_kuma_server is not None:
            self.kuma_ping.cancel()

    # Uptime Kuma Ping
    @tasks.loop(seconds=10)
    async def kuma_ping(self):
        await self.bot.wait_until_ready()

        # Send info to Uptime Kuma server
        async with aiohttp.ClientSession() as session:
            retry = 0

            while retry < 3:
                try:
                    if retry > 0:
                        logging.debug(f"[KUMA] Retrying ping... (retry {retry})")

                    # Ok if the bot is connected or if it was disconnected less than or 3 seconds ago
                    if self.bot.connected or (not self.bot.connected and (datetime.datetime.now() - self.bot.last_disconnect).seconds <= 3):
                        async with await session.get(
                            f"{self.bot.options['uptime-kuma-push']}?status=up&msg=OK&ping={round(self.bot.latency * 1000, 2)}"
                        ) as req:
                            json = await req.json()

                            if json["ok"]:
                                return
                            else:
                                logging.debug(
                                    f"[KUMA] Ping failed (status: {json}), trying again."
                                )
                                retry += 1
                    else:
                        async with await session.get(
                            f"{self.bot.options['uptime-kuma-push']}?status=down&msg=DISCONNECTED"
                        ) as req:
                            json = await req.json()

                            if json["ok"]:
                                return
                            else:
                                logging.debug(
                                    f"[KUMA] Ping failed (status: {json}), trying again."
                                )
                                retry += 1
                except Exception:
                    logging.debug("[KUMA] Ping failed. Trying again.")
                    logging.debug(traceback.format_exc())
                    retry += 1

            logging.error("[KUMA] Ping failed 3 times, giving up this time.\n")
            return


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(UptimeKuma(bot))
