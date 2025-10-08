from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


async def defer(
    bot: "TitaniumBot", ctx: commands.Context["TitaniumBot"], ephemeral: bool = False
) -> None:
    """
    Defer the response to a command context. If an interaction, the interaction is deferred. If a message context, a reaction is added to indicate loading.
    """
    if ctx.interaction is not None:
        await ctx.defer(ephemeral=ephemeral)
    else:
        show_loading = True

        if ctx.guild is not None:
            # Get server config
            server_config = bot.guild_configs.get(ctx.guild.id)

            if server_config is not None:
                show_loading = server_config.loading_reaction

        if not show_loading:
            return

        await ctx.message.add_reaction(bot.loading_emoji)


async def stop_loading(
    bot: "TitaniumBot", ctx: commands.Context["TitaniumBot"]
) -> None:
    try:
        show_loading = True

        if ctx.guild is not None:
            # Get server config
            server_config = bot.guild_configs.get(ctx.guild.id)

            if server_config is not None:
                show_loading = server_config.loading_reaction

        if not show_loading:
            return

        await ctx.message.remove_reaction(bot.loading_emoji, ctx.me)
    except (discord.HTTPException, discord.Forbidden, discord.NotFound, TypeError):
        pass

    return
