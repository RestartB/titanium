import discord
from discord import app_commands
from discord.ext import commands


class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="hello")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title="Hello!")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Example(bot))
