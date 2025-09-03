import base64
from typing import TYPE_CHECKING, Literal

import discord
from discord import Color, Embed, app_commands
from discord.ext import commands

from lib.views.feedback_modal import FeedbackModal

if TYPE_CHECKING:
    from main import TitaniumBot


class UtilityCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot

    @app_commands.command(
        name="feedback", description="Share any suggestions or feedback."
    )
    async def feedback(self, interaction: discord.Interaction["TitaniumBot"]) -> None:
        """
        This command allows you to provide feedback or share your suggestions or maybe any bug/issue with the bot's developers.
        """
        modal = FeedbackModal()
        await interaction.response.send_modal(modal)

    @commands.hybrid_command(name="banner", description="Get the banner of a user.")
    @app_commands.describe(user="The user whose banner you want to see.")
    async def banner(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: discord.Member | discord.User = None,
    ) -> None:
        """
        Get the banner of a user and display it in an embed.
        """
        await ctx.defer()

        user = user or ctx.author
        user_obj = await ctx.bot.fetch_user(user.id)
        banner = user_obj.banner.url if user_obj.banner else None

        e = Embed(color=Color.blue())

        if banner:
            e.set_author(
                name=f"@{user.name}'s Banner",
                icon_url=user.avatar.url if user.avatar else user.default_avatar.url,
            )
            e.set_image(url=banner)
            png_url = banner + "?format=png"
            jpg_url = banner + "?format=jpg"
            webp_url = banner + "?format=webp"
            e.description = f"**Open URL: [`PNG`]({png_url}) | [`JPG`]({jpg_url}) | [`WEBP`]({webp_url})**"
        else:
            e.description = (
                f"{str(self.bot.error_emoji)} This user does not have a banner."
            )
            e.color = Color.red()

        await ctx.reply(embed=e)

    @commands.hybrid_command(
        name="membercount",
        aliases=["memcount", "mcount"],
        description="Get current server member count.",
    )
    @commands.guild_only()
    @app_commands.guild_only()
    async def members_count(self, ctx: commands.Context["TitaniumBot"]) -> None:
        """
        Get the current count of members and bots in the server.
        """
        total_members = ctx.guild.member_count
        bot_count = sum(member.bot for member in ctx.guild.members)

        e = Embed(
            color=Color.blue(),
            title="👨‍👩‍👧‍👦 Member Counts",
            description=f"👨‍👩‍👧‍👦 Total Members: **{total_members}** | 🤖 Bot Count: **{bot_count}**",
        )
        await ctx.reply(embed=e)

    @commands.hybrid_command(
        name="base64", description="Convert text to base64 or decode base64 to text."
    )
    @app_commands.describe(
        text="Text to encode or decode.",
        mode="Choose 'encode' to convert text to base64, 'decode' to convert base64 to text.",
    )
    async def base64(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        text: str,
        mode: Literal["Encode", "Decode"] = "Encode",
    ) -> None:
        """
        Encode text to base64 or decode base64 to text.
        """

        await ctx.defer()

        try:
            if mode.lower() == "encode":
                encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
                e = Embed(
                    color=Color.blue(),
                    title="🔒 Base64 Encoded",
                    description=f"```{encoded[:3000]}```",
                )
                await ctx.reply(embed=e)
            elif mode.lower() == "decode":
                decoded = base64.b64decode(text.encode("utf-8")).decode("utf-8")
                e = Embed(
                    color=Color.blue(),
                    title="🔒 Base64 Decoded",
                    description=f"```{decoded[:3000]}```",
                )
                await ctx.reply(embed=e)
            else:
                e = Embed(
                    color=Color.red(),
                    title=f"{str(self.bot.error_emoji)} Error",
                    description="Invalid mode. Use 'Encode' or 'Decode'.",
                )
                await ctx.reply(embed=e)

        except Exception as e:
            e = Embed(
                color=Color.red(),
                title=f"{str(self.bot.error_emoji)} Error",
                description=f"{mode.capitalize()} failed due to: {e}",
            )
            await ctx.reply(embed=e)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(UtilityCog(bot))
