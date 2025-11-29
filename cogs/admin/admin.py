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

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        self.logger: logging.Logger = logging.getLogger("admin")

    @commands.group(name="admin", hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def admin_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    @admin_group.command(name="exc", hidden=True)
    @commands.is_owner()
    async def raise_exception(self, ctx: commands.Context["TitaniumBot"]) -> None:
        """Command to raise an exception for testing error logging."""
        try:
            raise ValueError("This is a test exception for error logging.")
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="clear", hidden=True)
    @commands.is_owner()
    async def clear_console(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await defer(ctx, ephemeral=True)

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
            self.logger.error("Error clearing console", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Clearing Console",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="sync", hidden=True)
    @commands.is_owner()
    async def warn(
        self,
        ctx: commands.Context["TitaniumBot"],
    ) -> None:
        await defer(ctx, ephemeral=True)

        # Sync commands
        self.logger.info("Syncing commands...")
        try:
            tree = await self.bot.tree.sync()
            self.logger.info(f"Synced {len(tree)} commands.")

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Commands Synced",
                    description=f"Synced {len(tree)} commands.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
            await ctx.message.remove_reaction(self.bot.loading_emoji, ctx.me)
        except discord.HTTPException as e:
            self.logger.error("Failed to sync commands.", exc_info=e)

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
            await stop_loading(ctx)

    @admin_group.command(name="reload", hidden=True)
    @commands.is_owner()
    async def reload_cogs(self, ctx: commands.Context["TitaniumBot"], cog: str) -> None:
        await defer(ctx, ephemeral=True)

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
            self.logger.error(f"Error reloading {cog}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Reloading",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="load", hidden=True)
    @commands.is_owner()
    async def load_cog(self, ctx: commands.Context["TitaniumBot"], cog_name: str) -> None:
        await defer(ctx, ephemeral=True)

        try:
            await ctx.bot.load_extension(f"cogs.{cog_name}")
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.success_emoji} Loaded",
                    description=f"Successfully loaded `{cog_name}` cog.",
                    colour=discord.Colour.green(),
                )
            )
        except Exception as e:
            self.logger.error(f"Error loading {cog_name}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.error_emoji} Error Loading",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                )
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="unload", hidden=True)
    @commands.is_owner()
    async def unload_cog(self, ctx: commands.Context["TitaniumBot"], cog_name: str) -> None:
        await defer(ctx, ephemeral=True)

        try:
            await ctx.bot.unload_extension(f"cogs.{cog_name}")
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.success_emoji} Unloaded",
                    description=f"Successfully unloaded `{cog_name}` cog.",
                    colour=discord.Colour.green(),
                )
            )
        except Exception as e:
            self.logger.error(f"Error unloading {cog_name}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{self.bot.error_emoji} Error Unloading",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                )
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="migrate-db", hidden=True)
    @commands.is_owner()
    async def migrate_db(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await defer(ctx, ephemeral=True)

        try:
            from lib.sql.sql import init_db

            await init_db()
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Database Migrated",
                    description="Database migrations completed successfully.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error("Error migrating database", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Migrating Database",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="reloadserver", aliases=["reload-server"], hidden=True)
    @commands.is_owner()
    async def reload_server(self, ctx: commands.Context["TitaniumBot"], guild_id: int) -> None:
        """Reload a guild's configuration from the database."""
        await defer(ctx, ephemeral=True)

        try:
            await self.bot.refresh_guild_config_cache(guild_id)
            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Server Reloaded",
                    description=f"Successfully reloaded configuration for guild ID `{guild_id}`.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error reloading server {guild_id}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Reloading Server",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="unlockuser", aliases=["unlock-user"], hidden=True)
    @commands.is_owner()
    async def unlock_user(self, ctx: commands.Context["TitaniumBot"], user_id: int) -> None:
        await defer(ctx, ephemeral=True)

        try:
            for server in self.bot.punishing:
                if user_id in self.bot.punishing[server]:
                    self.bot.punishing[server].remove(user_id)
                    await ctx.reply(
                        embed=discord.Embed(
                            title=f"{str(self.bot.success_emoji)} User Unlocked",
                            description=f"Successfully unlocked user ID `{user_id}`.",
                            colour=discord.Colour.green(),
                        ),
                        ephemeral=True,
                    )
            else:
                await ctx.reply(
                    embed=discord.Embed(
                        title=f"{str(self.bot.error_emoji)} User Not Locked",
                        description=f"User ID `{user_id}` is not locked.",
                        colour=discord.Colour.red(),
                    ),
                    ephemeral=True,
                )
        except Exception as e:
            self.logger.error(f"Error unlocking user {user_id}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Unlocking User",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="debuglogs", aliases=["debug-logs", "debuglog"], hidden=True)
    @commands.is_owner()
    async def debug_logs(self, ctx: commands.Context["TitaniumBot"], logger: str) -> None:
        await defer(ctx, ephemeral=True)

        try:
            target_logger = logging.getLogger(logger)
            target_logger.setLevel(logging.DEBUG)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Log Level Changed",
                    description=f"Enabled debug logging for `{logger}`.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error changing log level for {logger}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Changing Log Level",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="info_logs", aliases=["info-logs", "infolog"], hidden=True)
    @commands.is_owner()
    async def info_logs(self, ctx: commands.Context["TitaniumBot"], logger: str) -> None:
        await defer(ctx, ephemeral=True)

        try:
            target_logger = logging.getLogger(logger)
            target_logger.setLevel(logging.INFO)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Log Level Changed",
                    description=f"Enabled info logging for `{logger}`.",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error changing log level for {logger}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Changing Log Level",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)

    @admin_group.command(name="getserverowner", aliases=["get-server-owner"], hidden=True)
    @commands.is_owner()
    async def get_server_owner(self, ctx: commands.Context["TitaniumBot"], guild_id: int) -> None:
        """Get the owner ID of a specified server."""
        await defer(ctx, ephemeral=True)

        try:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                raise ValueError(f"Guild with ID {guild_id} not found.")

            if guild.owner_id is None:
                raise ValueError(f"Guild with ID {guild_id} has no owner ID.")

            owner = guild.owner

            if owner is None:
                owner = await self.bot.fetch_user(guild.owner_id)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.success_emoji)} Server Owner",
                    description=f"`@{owner.name}` (`{owner.id}`)",
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error retrieving owner for server {guild_id}", exc_info=e)

            await ctx.reply(
                embed=discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Error Retrieving Server Owner",
                    description=f"```python\n{traceback.format_exc()}```",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        finally:
            await stop_loading(ctx)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AdminCog(bot))
