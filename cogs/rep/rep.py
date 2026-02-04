import re
from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Interaction
from discord.ext import commands
from discord.ui import Button, View, button

if TYPE_CHECKING:
    from main import TitaniumBot


class RepView(View):
    def __init__(
        self,
        bot: TitaniumBot,
        target_member: discord.Member,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target_member = target_member

    @button(label="Give Rep", emoji="➕", style=ButtonStyle.green)
    async def give_rep(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not interaction.message:
            return

        await interaction.response.defer()
        await interaction.message.edit(
            embed=discord.Embed(
                description=f"{self.bot.success_emoji} **1 rep** given to {self.target_member.mention}",
                colour=discord.Colour.green(),
            ),
            view=None,
        )


class RepTestCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        matches = []
        for check_word in ["thank you", "thx", "thanks"]:
            pattern = r"\b" + re.escape(check_word) + r"\b"
            matches.extend(re.findall(pattern, message.content.lower()))

        if not matches:
            return

        if isinstance(message.author, discord.User):
            return

        view = RepView(bot=self.bot, target_member=message.author)
        await message.reply(view=view, mention_author=False)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(RepTestCog(bot))
