import discord
from discord import Color, app_commands
from discord.ext import commands


class NixCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Nix command
    @app_commands.command(
        name="nix-checker", description="Check for nix in your messages."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(check="The string to check.")
    async def nix(self, interaction: discord.Interaction, check: str):
        await interaction.response.defer(ephemeral=True)

        if "nix" in check.lower():
            embed = discord.Embed(
                title="Warning!",
                description="This message contains nix!",
                color=Color.red(),
            )
        else:
            embed = discord.Embed(
                title="Clear!",
                description="This message doesn't contain nix.",
                color=Color.green(),
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(NixCheck(bot))
