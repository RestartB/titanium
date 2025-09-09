import logging
import os
import traceback
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from lib.helpers.hybrid_adapters import defer, stop_loading

if TYPE_CHECKING:
    from main import TitaniumBot


class AdminCog(commands.Cog):
    """Private bot admin only commands"""
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.group(name="admin", hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def admin_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.send_help(
            ctx.command
        )  # send group help if does not match nay subcommands.

    @admin_group.command(name="clear", hidden=True)
    @commands.is_owner()
    async def clear_console(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await defer(self.bot, ctx, ephemeral=True)

        try:
            os.system("cls" if os.name == "nt" else "clear")
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Console Cleared",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            logging.error(f"Error clearing console: {e}")
            logging.error(traceback.format_exc())

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Clearing Console",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(self.bot, ctx)

    @admin_group.command(name="sync", hidden=True)
    @commands.is_owner()
    async def warn(
        self,
        ctx: commands.Context["TitaniumBot"],
    ) -> None:
        await defer(self.bot, ctx, ephemeral=True)

        # Sync commands
        logging.info("[SYNC] Syncing commands...")
        try:
            tree = await self.bot.tree.sync()
            logging.info(f"[SYNC] Synced {len(tree)} commands.")

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Commands Synced",
                    description=f"Synced {len(tree)} commands.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
            await ctx.message.remove_reaction(self.bot.loading_emoji, ctx.me)
        except discord.HTTPException:
            logging.error("[SYNC] Failed to sync commands.")
            logging.error(traceback.format_exc())

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Failed to sync",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
            await ctx.message.remove_reaction(self.bot.loading_emoji, ctx.me)
        finally:
            await stop_loading(self.bot, ctx)

    @admin_group.command(name="reload", hidden=True)
    @commands.is_owner()
    async def reload_cogs(self, ctx: commands.Context["TitaniumBot"], cog: str) -> None:
        await defer(self.bot, ctx, ephemeral=True)

        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Reloaded",
                    description=f"Successfully reloaded `{cog}`.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            logging.error(f"Error reloading {cog}: {e}")
            logging.error(traceback.format_exc())

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Reloading",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(self.bot, ctx)

    @admin_group.command(name="unload", hidden=True)
    @commands.is_owner()
    async def unload_cog(
        self, ctx: commands.Context["TitaniumBot"], cog_name: str
    ) -> None:
        # As it is a prefix command no need of defer.
        try:
            await ctx.bot.unload_extension(f"cogs.{cog_name}")
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.success_emoji} Unloaded",
                    description=f"Successfully unloaded `{cog_name}` cog.",
                    colour=discord.Colour.green(),
                )
            )
        except Exception as exc:
            logging.error(f"Error unloading {cog_name}: {exc}")
            logging.error(traceback.format_exc())

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.error_emoji} Error Unloading",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                )
            )


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(AdminCog(bot))
