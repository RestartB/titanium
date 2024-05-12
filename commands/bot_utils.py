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

class bot_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    botGroup = app_commands.Group(name="bot", description="Bot related commands.")
    
    # Ping command
    @botGroup.command(name = "ping", description = "Ping the bot.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "Pong!")
        embed.add_field(name = "Latency", value = f"{round(self.bot.latency*1000, 2)}ms")
        await interaction.followup.send(embed = embed)

    # Info command
    @botGroup.command(name = "info", description = "Info about the bot.")
    async def info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title = "Info")
        embed.add_field(name = "Credit", value = "Bot created by Restart (<@563372552643149825>)\n\nBot Framework\n[discord.py](https://github.com/Rapptz/discord.py)\n\nAPIs and Modules:\n[Cat API](https://thecatapi.com/)\n[Dog API](https://dog.ceo/dog-api/)\n[Lyrics API](https://lrclib.net/)\n[Spotipy Module](https://github.com/spotipy-dev/spotipy)\n[Wikipedia Module](https://github.com/goldsmith/Wikipedia)")
        await interaction.followup.send(embed = embed)

    # Host Info command
    @botGroup.command(name = "host-info", description = "Info about the bot host.")
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

    # Send Message command
    @botGroup.command(name = "send-message", description = "Admin Only: send debug message.")
    async def send_message(self, interaction: discord.Interaction, message: str, channel_id: str):
        await interaction.response.defer(ephemeral = True)
        
        if interaction.user.id in self.bot.dev_ids:
            channel = self.bot.get_channel(int(channel_id))
            await channel.send(message)

            await interaction.followup.send(f"Message sent to channel ID {channel_id}.\n\nContent: {message}", ephemeral = True)
        else:
            embed = discord.Embed(title = "You do not have permission to run this command.", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral = True)

async def setup(bot):
    await bot.add_cog(bot_utils(bot))