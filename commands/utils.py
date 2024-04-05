import discord
from discord import app_commands, Color
from discord.ext import commands
import datetime
from datetime import timedelta
import cpuinfo
import psutil
import os
import sys
import time

class utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Ping command
    @app_commands.command(name = "ping", description = "Ping the bot.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "Pong!")
        embed.add_field(name = "Latency", value = f"{round(self.bot.latency*1000, 2)}ms")
        await interaction.followup.send(embed = embed)

    # Restart Bot command
    @app_commands.command(name = "restart", description = "Restart the bot.")
    @commands.is_owner()
    async def restart(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "The bot will restart.", color = Color.green())
        await interaction.followup.send(embed = embed, ephemeral = True)
        os.execv(sys.executable, ['python'] + sys.argv)

    # Info command
    @app_commands.command(name = "info", description = "Info about the bot.")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "Info")
        embed.add_field(name = "Credit", value = "Bot created by Restart (<@563372552643149825>)\n\nBot Framework\n[discord.py](https://github.com/Rapptz/discord.py)\n\nAPIs and Modules:\n[Cat API](https://thecatapi.com/)\n[Dog API](https://dog.ceo/dog-api/)\n[Lyrics API](https://lrclib.net/)\n[Spotipy Module](https://github.com/spotipy-dev/spotipy)\n[Wikipedia Module](https://github.com/goldsmith/Wikipedia)")
        await interaction.followup.send(embed = embed)

    # PFP command
    @app_commands.command(name = "pfp", description = "Show a user's PFP.")
    async def pfp(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()
        # Idea: set embed colour to user's banner colour'
        embed = discord.Embed(title = f"PFP - {user.name}", color = Color.random())
        embed.set_image(url = user.avatar.url)
        embed.set_footer(text = f"Requested by {interaction.user.name} - right click or long press to save image", icon_url = interaction.user.avatar.url)
        # Send Embed
        await interaction.followup.send(embed = embed)
    
    # Host Info command
    @app_commands.command(name = "host-info", description = "Info about the bot host.")
    async def host_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        embed = discord.Embed(title = "Loading...", color = Color.random())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        embed = discord.Embed(title = "Host Info", color=Color.random())

        sec = timedelta(seconds=int(time.monotonic()))
        d = datetime.datetime(1,1,1) + sec

        sysinfo = cpuinfo.get_cpu_info()

        embed.add_field(name = "CPU Name", value = sysinfo['brand_raw'], inline = False)
        embed.add_field(name = "Percent CPU Usage", value = psutil.cpu_percent(), inline = False)
        embed.add_field(name = "Percent RAM Usage", value = psutil.virtual_memory().percent, inline = False)
        embed.add_field(name = "System Uptime", value = ("%d:%d:%d:%d" % (d.day-1, d.hour, d.minute, d.second)), inline = False)
        embed.add_field(name = "OS Name", value = os.name, inline = False)
        embed.add_field(name = "Python Version", value = sysinfo['python_version'])
        embed.add_field(name = "Bot Latency", value = f"{round(self.bot.latency*1000, 2)}ms", inline = False)
        
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)

        await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(utils(bot))