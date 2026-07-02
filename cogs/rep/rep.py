import re
from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Interaction
from discord.ext import commands
from discord.ui import Button, View, button
from sqlalchemy.dialects.postgresql import insert

from lib.sql.sql import RepAddHistory, UserRep, get_session

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
        if not interaction.message or not interaction.guild_id:
            return

        await interaction.response.defer()

        async with get_session() as session:
            session.add(
                RepAddHistory(
                    user_id=interaction.user.id,
                    target_id=self.target_member.id,
                    guild_id=interaction.guild_id,
                )
            )

            stmt = insert(UserRep).values(
                guild_id=interaction.guild_id,
                user_id=self.target_member.id,
                rep=1,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["guild_id", "user_id"],
                set_={
                    "rep": UserRep.rep + 1,
                },
            ).returning(UserRep)

            rep = (await session.execute(stmt)).scalar_one()

        await interaction.message.edit(
            embed=discord.Embed(
                description=f"{self.bot.success_emoji} **1 rep** given to {self.target_member.mention} (`{rep.rep}` rep total)",
                colour=discord.Colour.green(),
            ),
            view=None,
        )

    @button(emoji="🗑️", style=ButtonStyle.grey)
    async def delete_button(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not interaction.message:
            return

        await interaction.response.defer(ephemeral=True)
        await interaction.delete_original_response()


class RepTestCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # no reply / invalid reference - ignore
        if (
            not message.guild
            or not message.reference
            or not message.reference.resolved
            or isinstance(message.reference.resolved, discord.DeletedReferencedMessage)
            or message.reference.type != discord.MessageReferenceType.reply
        ):
            return

        # base settings
        guild_config = await self.bot.fetch_guild_config(message.guild.id)
        if (
            not guild_config
            or not guild_config.rep_enabled
            or not guild_config.rep_settings.rep_hint
        ):
            return

        matches = []
        for check_word in ["thank you", "thx", "thanks"]:
            pattern = r"\b" + re.escape(check_word) + r"\b"
            matches.extend(re.findall(pattern, message.reference.resolved.content.lower()))

        if not matches:
            return

        if isinstance(message.reference.resolved.author, discord.User):
            return

        view = RepView(bot=self.bot, target_member=message.reference.resolved.author)
        await message.reply(view=view, mention_author=False, delete_after=60)


async def setup(bot: TitaniumBot) -> None:
    return
    # await bot.add_cog(RepTestCog(bot))
