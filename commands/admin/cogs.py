import logging
import traceback

import discord
from discord.ext import commands

from ...main import TitaniumBot


class AdminCog(commands.Cog):
    def __init__(self, bot: TitaniumBot):
        self.bot = bot

    @commands.hybrid_command(name="sync")
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
                    title="Commands Synced",
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
                    title="Failed to Sync",
                    description=f"```python\n{traceback.format_exc()}```",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
