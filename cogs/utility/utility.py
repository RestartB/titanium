import base64
from typing import TYPE_CHECKING, Literal

import discord
from discord import Color, Embed, app_commands, Optional
from discord.ext import commands

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


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(UtilityCog(bot))
