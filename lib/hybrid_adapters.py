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
    content: str = "",
    embed: Embed | None = None,
    view: View | None = None,
    ephemeral: bool = False,
    remove_loading: bool = True,
) -> None:
    """
    Replies to a context. Auto decides between interaction and message context.
    """
    if ctx.interaction is not None:
        if embed is not None and view is not None:
            await ctx.interaction.followup.send(
                content=content, embed=embed, view=view, ephemeral=ephemeral
            )
        elif embed is not None:
            await ctx.interaction.followup.send(
                content=content, embed=embed, ephemeral=ephemeral
            )
        elif view is not None:
            await ctx.interaction.followup.send(
                content=content, view=view, ephemeral=ephemeral
            )
        else:
            await ctx.interaction.followup.send(content=content, ephemeral=ephemeral)
    else:
        if embed is not None and view is not None:
            await ctx.reply(content=content, embed=embed, view=view)
        elif embed is not None:
            await ctx.reply(content=content, embed=embed)
        elif view is not None:
            await ctx.reply(content=content, view=view)
        else:
            await ctx.reply(content=content)

        if remove_loading and ctx.guild:
            await ctx.message.remove_reaction("✅", ctx.guild.me)
