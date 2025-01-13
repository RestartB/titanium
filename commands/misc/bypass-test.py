import discord
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class BypassTest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Bypass test command
    @app_commands.command(name = "bypass-test", description = "Test bypass for external apps.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def nix(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed = discord.Embed(title = "Bypass Test", description="Press below to test the bypass.", color = Color.green())

        class BypassView(View):
            def __init__(self):
                super().__init__()
            
            @discord.ui.button(label="Test Bypass", style=discord.ButtonStyle.primary)
            async def test_bypass(self, button: discord.ui.Button, interaction: discord.Interaction):
                await 
                await interaction.followup.send("Can you see me?", ephemeral=False)
        
        await interaction.followup.send(embed=embed, view=BypassView())

async def setup(bot):
    await bot.add_cog(BypassTest(bot))