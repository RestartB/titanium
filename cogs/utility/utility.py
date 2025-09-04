import base64
from typing import TYPE_CHECKING

from discord import Color, Embed, app_commands
from discord.ext import commands

from lib.views.feedback_modal import FeedbackModal

if TYPE_CHECKING:
    from main import TitaniumBot


class UtilityCog(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot

    @commands.hybrid_command(
        name="membercount",
        aliases=["memcount", "mcount"],
        description="Get current server member count.",
    )
    @commands.guild_only()
    async def members_count(self, ctx: commands.Context["TitaniumBot"]) -> None:
        """
        Get the current count of members and bots in the server.
        """

        # make the type checker happy
        if not ctx.guild:
            return

        total_members = ctx.guild.member_count
        bot_count = sum(member.bot for member in ctx.guild.members)

        e = Embed(
            color=Color.blue(),
            title="👨‍👩‍👧‍👦 Member Counts",
            description=f"👨‍👩‍👧‍👦 Total Members: **{total_members}** | 🤖 Bot Count: **{bot_count}**",
        )
        await ctx.reply(embed=e)

    @commands.hybrid_group(name="base64", description="Base64 encoding and decoding.")
    async def base64_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        await ctx.send_help(ctx.command)

    @base64_group.command(name="encode", description="Convert text to Base64.")
    @app_commands.describe(
        text="Text to encode to Base64.",
    )
    async def base64_encode(
        self,
        ctx: commands.Context["TitaniumBot"],
        text: str,
    ) -> None:
        """
        Encode text to Base64.
        """

        await ctx.defer()

        encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
        e = Embed(
            color=Color.blue(),
            title="🔒 Base64 Encoded",
            description=f"```{encoded[:3000]}```",
        )
        await ctx.reply(embed=e)

    @base64_group.command(name="decode", description="Convert text from Base64.")
    @app_commands.describe(
        base_64="Base64 to convert to text.",
    )
    async def base64_decode(
        self,
        ctx: commands.Context["TitaniumBot"],
        base_64: str,
    ) -> None:
        """
        Decode Base64 to text.
        """

        await ctx.defer()

        decoded = base64.b64decode(base_64.encode("utf-8")).decode("utf-8")
        e = Embed(
            color=Color.blue(),
            title="🔒 Base64 Decoded",
            description=f"```{decoded[:3000]}```",
        )
        await ctx.reply(embed=e)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(UtilityCog(bot))
