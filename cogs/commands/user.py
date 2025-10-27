from typing import TYPE_CHECKING

from discord import ButtonStyle, Colour, Embed, Member, Optional, User, app_commands
from discord.ext import commands
from discord.ui import Button, View

if TYPE_CHECKING:
    from main import TitaniumBot


class UserCommandsCog(commands.Cog):
    """User related commands"""

    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot

    @commands.hybrid_command(name="pfp", description="Get a user's profile picture.")
    async def pfp(
        self, ctx: commands.Context["TitaniumBot"], user: Optional[User | Member]
    ) -> None:
        await ctx.defer()

        if not user:
            user = ctx.author

        embed = Embed(colour=user.accent_colour)
        embed.set_author(
            name=f"@{user.name}'s PFP",
            icon_url=user.display_avatar.url,
        )

        embed.set_image(url=user.display_avatar.url)

        png_url = user.display_avatar.url + "?format=png"
        jpg_url = user.display_avatar.url + "?format=jpg"
        webp_url = user.display_avatar.url + "?format=webp"
        formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

        view = View()
        for format_name, format_url in formats.items():
            view.add_item(Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link))

        await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(name="server-pfp", description="Get a user's server profile picture.")
    @commands.guild_only()
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
            embed.description = f"{user.mention} does not have a server profile picture."
            await ctx.reply(embed=embed)

    @commands.hybrid_command(name="banner", description="Get the banner of a user.")
    @app_commands.describe(user="The user whose banner you want to see.")
    async def banner(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: Optional[Member | User],
    ) -> None:
        """
        Get the banner of a user and display it in an embed.
        """
        await ctx.defer()

        user = user or ctx.author
        user_obj = await ctx.bot.fetch_user(user.id)
        banner = user_obj.banner.url if user_obj.banner else None

        e = Embed(colour=user.accent_colour)

        if banner:
            e.set_author(
                name=f"@{user.name}'s Banner",
                icon_url=user.display_avatar.url,
            )
            e.set_image(url=banner)

            png_url = banner + "?format=png"
            jpg_url = banner + "?format=jpg"
            webp_url = banner + "?format=webp"
            formats = {"PNG": png_url, "JPG": jpg_url, "WEBP": webp_url}

            view = View()
            for format_name, format_url in formats.items():
                view.add_item(
                    Button(label=f"{format_name}", url=format_url, style=ButtonStyle.link)
                )

            await ctx.reply(embed=e, view=view)
        else:
            e.description = f"{str(self.bot.error_emoji)} This user does not have a banner."
            e.colour = Colour.red()

            await ctx.reply(embed=e)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(UserCommandsCog(bot))
