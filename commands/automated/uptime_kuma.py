import logging
import traceback

import aiohttp
from discord.ext import commands, tasks


class UptimeKuma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        try:
            self.uptimeKumaServer = bot.options["uptime-kuma-push"]
            logging.info("[KUMA] Starting Uptime Kuma pinger...")
            self.kumaPing.start()
        except KeyError:
            logging.info("[KUMA] Disabling the Uptime Kuma pinger, no Uptime Kuma server was specified.")
            self.uptimeKumaServer = None
    
    def cog_unload(self):
        if self.uptimeKumaServer is not None:
            self.kumaPing.cancel()
    
    # Uptime Kuma Ping
    @tasks.loop(seconds=10)
    async def kumaPing(self):
        # Send info to Uptime Kuma server
        async with aiohttp.ClientSession() as session:
            retry = 0
            
            while retry < 3:
                try:
                    if retry > 0:
                        logging.debug(f"[KUMA] Retrying ping... (retry {retry})")
                    
                    if not self.bot.is_closed():
                        async with await session.get(f"{self.bot.options["uptime-kuma-push"]}/api/push/iaHDSrJnaq?status=up&msg=OK&ping={round(self.bot.latency*1000, 2)}") as req:
                            json = await req.json()

                            if json["ok"] == True:
                                return
                            else:
                                logging.debug(f"[KUMA] Ping failed (status: {json}), trying again.")
                                retry += 1
                    else:
                        async with await session.get(f"{self.bot.options["uptime-kuma-push"]}/api/push/iaHDSrJnaq?status=down&msg=DISCONNECTED") as req:
                            json = await req.json()
                            
                            if json["ok"] == True:
                                return
                            else:
                                logging.debug(f"[KUMA] Ping failed (status: {json}), trying again.")
                                retry += 1
                except Exception as e:
                    logging.debug(f"[KUMA] Ping failed. Trying again.")
                    logging.debug(traceback.format_exc())
                    retry += 1
            
            logging.error("[KUMA] Ping failed 3 times, giving up this time.\n")
            return

async def setup(bot):
    await bot.add_cog(UptimeKuma(bot))