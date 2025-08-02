import logging
import traceback
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from ...main import TitaniumBot


class AdminCogsCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="sync", hidden=True)
    @commands.is_owner()
    async def warn(
        self,
        ctx: commands.Context[commands.Bot],
    ) -> None:
        await ctx.defer(ephemeral=True)

        # Sync commands
        logging.info("[SYNC] Syncing commands...")
        try:
            tree = await self.bot.tree.sync()
            logging.info(f"[SYNC] Synced {len(tree)} commands.")

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Commands Synced",
                    description=f"Synced {len(tree)} commands.",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
        except discord.HTTPException:
            logging.error("[SYNC] Failed to sync commands.")
            logging.error(traceback.format_exc())

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Failed to sync",
                    description=f"```python\n{traceback.format_exc()}```",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(AdminCogsCog(bot))
