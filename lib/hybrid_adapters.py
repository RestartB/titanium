from discord import Embed
from discord.ext import commands
from discord.ui import View


async def defer(ctx: commands.Context[commands.Bot], ephemeral: bool = False) -> None:
    """
    Defer the response to a command context. If an interaction, the interaction is deferred. If a message context, a reaction is added to indicate loading.
    """
    if ctx.interaction is not None:
        await ctx.defer(ephemeral=ephemeral)
    else:
        await ctx.message.add_reaction("✅")


async def reply(
    ctx: commands.Context[commands.Bot],
    embed: Embed,
    view: View,
    ephemeral: bool = False,
    remove_loading: bool = True,
) -> None:
    """
    Replies to a context. Auto decides between interaction and message context.
    """
    if ctx.interaction is not None:
        await ctx.interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
    else:
        await ctx.reply(embed=embed, view=view)
        if remove_loading:
            await ctx.message.remove_reaction("✅", ctx.guild.me)
