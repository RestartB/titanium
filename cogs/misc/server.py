from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Colour, app_commands
from discord.ext import commands
from discord.ui import Button, View

if TYPE_CHECKING:
    from main import TitaniumBot


class ServerCommandsCog(commands.Cog, name="Server", description="Get user information."):
    """Server related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="server", aliases=["serverinfo"], description="Get information about the server."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    async def server(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            title="Server Info",
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(name="Total Members", value=f"`{ctx.guild.member_count:,}`")
        embed.add_field(
            name="Creation Date", value=f"<t:{int(ctx.guild.created_at.timestamp())}:d>"
        )

        if ctx.guild.owner:
            embed.add_field(
                name="Owner",
                value=f"{ctx.guild.owner.mention} (`@{ctx.guild.owner.name}`)",
            )

        embed.add_field(
            name="Channels",
            value=f"`{len(ctx.guild.channels)}`",
        )
        embed.add_field(
            name="Categories",
            value=f"`{len(ctx.guild.categories)}`",
        )
        embed.add_field(
            name="Roles",
            value=f"`{len(ctx.guild.roles)}`",
        )

        embed.add_field(name="ID", value=f"`{ctx.guild.id}`")

        view = View()

        if ctx.guild.vanity_url:
            view.add_item(
                Button(
                    label="Vanity Invite",
                    url=ctx.guild.vanity_url,
                    style=ButtonStyle.url,
                )
            )

        await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(
        name="servericon", aliases=["icon"], description="Get the server's icon."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    async def servericon(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}'s Icon",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if not ctx.guild.icon:
            embed.description = "This server does not have an icon."
            await ctx.reply(embed=embed)
            return

        image = ctx.guild.icon.url
        embed.set_image(url=image)

        png_url = image + "?format=png"
        jpg_url = image + "?format=jpg"
        webp_url = image + "?format=webp"
        formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

        view = View()
        for format_name, format_url in formats.items():
            view.add_item(Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link))

        await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(
        name="boosts", aliases=["boostinfo"], description="Get the server's boost information."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @commands.guild_only()
    async def server_boosts(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.defer()

        if not ctx.guild:
            raise commands.errors.NoPrivateMessage

        embed = discord.Embed(
            title="Server Boosts",
            colour=ctx.guild.me.accent_colour if ctx.guild.me else Colour.random(),
        )
        embed.set_author(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        embed.add_field(name="Total Boosts", value=f"`{ctx.guild.premium_subscription_count}`")
        embed.add_field(name="Boost Level", value=f"`Level {ctx.guild.premium_tier}`", inline=True)

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ServerCommandsCog(bot))
