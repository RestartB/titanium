import logging
import traceback

import discord
from discord.ext import commands, tasks


class StatusUpdate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_update.start()

    def cog_unload(self):
        self.status_update.cancel()

    # Uptime Kuma Ping
    @tasks.loop(hours=1)
    async def status_update(self):
        await self.bot.wait_until_ready()

        try:
            app_data: discord.AppInfo = await self.bot.application_info()
            user_installs = app_data.approximate_user_install_count

            # Update status
            await self.bot.change_presence(
                activity=discord.Activity(
                    status=discord.Status.online,
                    type=discord.ActivityType.custom,
                    name="custom",
                    state=f"{user_installs} users, {len(self.bot.guilds)} servers - use /",
                )
            )
        except Exception:
            logging.error(
                f"Failed to update status:\n\n```python\n{traceback.format_exc()}```"
            )


async def setup(bot):
    await bot.add_cog(StatusUpdate(bot))
