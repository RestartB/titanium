from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


@asynccontextmanager
async def defer(ctx: commands.Context[TitaniumBot], ephemeral: bool = False, stop_only=False):
    try:
        if not stop_only:
            await _defer(ctx, ephemeral)

        yield
    except Exception:
        raise
    finally:
        await _stop_loading(ctx)


async def _defer(ctx: commands.Context["TitaniumBot"], ephemeral: bool = False) -> None:
    if ctx.interaction is not None:
        await ctx.defer(ephemeral=ephemeral)
    else:
        show_loading = True

        if ctx.guild is not None:
            # Get server config
            server_config = ctx.bot.guild_configs.get(ctx.guild.id)

            if server_config is not None:
                show_loading = server_config.loading_reaction

        if not show_loading:
            return

        await ctx.message.add_reaction(ctx.bot.loading_emoji)


async def _stop_loading(ctx: commands.Context["TitaniumBot"]) -> None:
    if ctx.interaction:
        return

    try:
        show_loading = True

        if ctx.guild is not None:
            # Get server config
            server_config = ctx.bot.guild_configs.get(ctx.guild.id)

            if server_config is not None:
                show_loading = server_config.loading_reaction

        if not show_loading:
            return

        if ctx.bot.loading_emoji in [r.emoji for r in ctx.message.reactions]:
            await ctx.message.remove_reaction(ctx.bot.loading_emoji, ctx.me)
    except discord.HTTPException, discord.Forbidden, discord.NotFound, TypeError:
        pass

    return


class SlashCommandOnly(commands.CommandError):
    """Exception for when a command is only available as slash command"""


class GroupCommandNotFoundException(commands.CommandError):
    """Exception raised when a command is not found in a hybrid group."""

    def __init__(self, command_name: str) -> None:
        super().__init__(f"The command {command_name} does not exist.")
        self.command_name = command_name


def handle_group_command_not_found(ctx: commands.Context["TitaniumBot"]):
    content = ctx.message.content
    prefix = ctx.prefix or ""

    if prefix and content.startswith(prefix):
        content = content[len(prefix) :]

    parts = content.strip().split(maxsplit=2)
    command_name = " ".join(parts[:2]) if len(parts) >= 2 else (ctx.invoked_with or "")

    raise GroupCommandNotFoundException(command_name)
