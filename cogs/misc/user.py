from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Embed, Member, Optional, User, app_commands
from discord.ext import commands
from discord.ui import Button, View

if TYPE_CHECKING:
    from main import TitaniumBot


class UserCommandsCog(commands.Cog, name="Users", description="Get user information."):
    """User related commands"""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="user", aliases=["userinfo"], description="Get information about a user."
    )
    @app_commands.describe(
        user="Optional: the user to get information about. Defaults to yourself."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def user(
        self, ctx: commands.Context["TitaniumBot"], user: Optional[User | Member]
    ) -> None:
        await ctx.defer()

        user = user or ctx.author

        in_guild = False
        if ctx.guild:
            in_guild = True if ctx.guild.get_member(user.id) else False

        user = await ctx.bot.fetch_user(user.id)

        creation_date = int(user.created_at.timestamp())
        join_date = (
            int(user.joined_at.timestamp()) if isinstance(user, Member) and user.joined_at else None
        )

        embed = Embed(title="User Info", colour=user.accent_colour)
        embed.set_author(
            name=f"{user.display_name} (@{user.name})",
            icon_url=user.display_avatar.url,
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        if user.banner is not None:
            embed.set_image(url=user.banner.url)

        embed.add_field(name="ID", value=f"`{user.id}`")
        embed.add_field(
            name="Joined Discord",
            value=f"<t:{creation_date}:R> (<t:{creation_date}:f>)",
        )
        if join_date:
            embed.add_field(
                name="Joined Server",
                value=f"<t:{join_date}:R> (<t:{join_date}:f>)",
            )

        if isinstance(user, Member) and ctx.guild:
            embed.add_field(
                name="Roles",
                value=", ".join(role.mention for role in user.roles if role.id != ctx.guild.id)
                or "No Roles",
            )

        if ctx.interaction and ctx.interaction.is_user_integration():
            embed.set_footer(
                text=f"@{ctx.author.name} - add Titanium to the server for more info",
                icon_url=ctx.author.display_avatar.url,
            )
        elif not in_guild:
            embed.set_footer(
                text=f"@{ctx.author.name} - user isn't in the server, showing limited info",
                icon_url=ctx.author.display_avatar.url,
            )
        else:
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

        view = View()
        view.add_item(
            discord.ui.Button(
                label="User URL",
                style=discord.ButtonStyle.url,
                url=f"https://discord.com/users/{user.id}",
                row=0,
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Open PFP in Browser",
                style=discord.ButtonStyle.url,
                url=user.display_avatar.url,
                row=0,
            )
        )

        # Send Embed
        await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(name="pfp", description="Get a user's profile picture.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def pfp(
        self, ctx: commands.Context["TitaniumBot"], user: Optional[User | Member]
    ) -> None:
        await ctx.defer()

        user = user or ctx.author
        user = await ctx.bot.fetch_user(user.id)

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s PFP",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        url = user.avatar.url if user.avatar else user.default_avatar.url

        embed.set_image(url=url)

        png_url = url + "?format=png"
        jpg_url = url + "?format=jpg"
        webp_url = url + "?format=webp"
        formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

        view = View()
        for format_name, format_url in formats.items():
            view.add_item(Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link))

        await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(name="server-pfp", description="Get a user's server profile picture.")
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=True)
    async def server_pfp(
        self, ctx: commands.Context["TitaniumBot"], user: Optional[Member]
    ) -> None:
        await ctx.defer()

        if not user:
            user = ctx.author if isinstance(ctx.author, Member) else None

        if not user:
            raise Exception("Member object not returned")

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s Server PFP",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if user.guild_avatar:
            embed.set_image(url=user.guild_avatar.url)

            png_url = user.guild_avatar.url + "?format=png"
            jpg_url = user.guild_avatar.url + "?format=jpg"
            webp_url = user.guild_avatar.url + "?format=webp"
            formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

            view = View()
            for format_name, format_url in formats.items():
                view.add_item(
                    Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link)
                )

            await ctx.reply(embed=embed, view=view)
        else:
            embed.description = (
                f"{self.bot.error_emoji} {user.mention} does not have a server profile picture."
            )
            await ctx.reply(embed=embed)

    @commands.hybrid_command(name="banner", description="Get the banner of a user.")
    @app_commands.describe(user="The user to get the banner of.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def banner(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: Optional[Member | User],
    ) -> None:
        await ctx.defer()

        user = user or ctx.author
        user = await ctx.bot.fetch_user(user.id)
        banner = user.banner.url if user.banner else None

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s Banner",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        if banner:
            embed.set_image(url=banner)

            png_url = banner + "?format=png"
            jpg_url = banner + "?format=jpg"
            webp_url = banner + "?format=webp"
            formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

            view = View()
            for format_name, format_url in formats.items():
                view.add_item(
                    Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link)
                )

            await ctx.reply(embed=embed, view=view)
        else:
            embed.description = f"{self.bot.error_emoji} {user.mention} does not have a banner."
            await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(UserCommandsCog(bot))
