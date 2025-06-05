from typing import TYPE_CHECKING

import discord
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View

if TYPE_CHECKING:
    from main import TitaniumBot


# Mafia Join View
class MafiaJoinView(View):
    def __init__(self, role: discord.Role) -> None:
        super().__init__(timeout=900)
        self.role = role

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.dm_channel is None:
            dm_channel = await interaction.user.create_dm()
        else:
            dm_channel = interaction.user.dm_channel

        embed = discord.Embed(
            title="Mafia",
            description="Titanium is testing your DMs. Please ensure Titanium can DM you during the game so you recieve updates on your survival.",
            color=Color.green(),
        )
        await dm_channel.send(embed=embed)

        await interaction.user.add_roles(
            self.role, reason="Titanium - Add user to Mafia game."
        )

        embed = discord.Embed(
            title="Mafia",
            description="You have joined the mafia game.",
            color=Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)

        await interaction.user.remove_roles(
            self.role, reason="Titanium - Remove user from Mafia game."
        )

        embed = discord.Embed(
            title="Mafia",
            description="You have left the mafia game.",
            color=Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class Mafia(commands.Cog):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot = bot
        self.running_games: list[int] = []

        # self.mafia_pool: asqlite.Pool = bot.mafia_pool

    # Start Mafia game command
    @app_commands.command(
        name="start", description="Start a mafia game in the set mafia category."
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def mafia_start(
        self, interaction: discord.Interaction, location: app_commands.Choice[str]
    ):
        await interaction.response.defer()

        channel = await interaction.guild.create_text_channel(
            name="mafia-game", reason="Titanium - Create automated mafia channel."
        )
        role = await interaction.guild.create_role(
            name=f"Mafia - {channel.id}",
            reason="Titanium - Create automated mafia role.",
        )

        embed = discord.Embed(
            title="Mafia",
            description=f"{interaction.user.mention} is starting a **Mafia** game in this channel. To join, press the Join button below.",
            color=Color.random(),
        )
        await channel.send(embed=embed, view=MafiaJoinView(role))

        embed = discord.Embed(
            title="Created",
            description=f"A mafia game has been created in {channel.mention}.",
            color=Color.green(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(Mafia(bot))
