from typing import TYPE_CHECKING

import discord
from discord import ButtonStyle, Colour, Interaction
from discord.ext.commands import CooldownMapping
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
        cooldowns: CooldownMapping,
        timeout: float = 60.0,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target_member = target_member
        self.cooldowns = cooldowns
        self.original_message: discord.Message | None

    @button(label="Give Rep", emoji="➕", style=ButtonStyle.green)
    async def give_rep(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not interaction.guild_id:
            return

        await interaction.response.defer(ephemeral=True)

        guild_config = await self.bot.fetch_guild_config(interaction.guild_id)
        if not guild_config or not guild_config.rep_enabled:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} Rep Disabled",
                description="The rep system is disabled in this server. Ask a server admin to turn it on using the `/settings` command or the Titanium Dashboard.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        bucket = self.cooldowns.get_bucket(
            {
                "giver_id": interaction.user.id,
                "receiver_id": self.target_member.id,
                "guild_id": interaction.guild_id,
            }
        )
        if not bucket:
            raise ValueError("No bucket returned")

        retry_after = bucket.update_rate_limit()
        if retry_after:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Cooldown",
                description=f"Please wait `{retry_after:.2f}s` before giving more rep to this user.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        async with get_session() as session:
            session.add(
                RepAddHistory(
                    user_id=interaction.user.id,
                    target_id=self.target_member.id,
                    guild_id=interaction.guild_id,
                    time=interaction.created_at,
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

        await interaction.followup.send(
            embed=discord.Embed(
                title=f"{self.bot.success_emoji} Done",
                description=f"**1 rep** given to {self.target_member.mention} (`{rep.rep}` rep total)",
                colour=Colour.green(),
            ),
            ephemeral=True,
        )

    @button(emoji="🗑️", style=ButtonStyle.grey)
    async def delete_button(self, interaction: Interaction["TitaniumBot"], button: Button):
        if not self.original_message:
            return

        await interaction.response.defer(ephemeral=True)

        if (
            self.original_message.author.id != interaction.user.id
            or not interaction.permissions.manage_messages
        ):
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Not Allowed",
                description="You didn't send this message. Only the message author or users with Manage Message permissions can delete the rep hint.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        await interaction.delete_original_response()
