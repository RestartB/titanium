import datetime
import platform
import time
from datetime import timedelta

import cpuinfo
import discord
import psutil
import pygit2
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class BotUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    botGroup = app_commands.Group(name="bot", description="Bot related commands.", allowed_contexts=context, allowed_installs=installs)
    
    # Ping command
    @botGroup.command(name = "ping", description = "Ping the bot.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def ping(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = "Pong!", color=Color.random())
        embed.add_field(name = "Latency", value = f"{round(self.bot.latency*1000, 2)}ms")
        
        await interaction.followup.send(embed = embed, ephemeral=ephemeral)
    
    # Invite command
    @botGroup.command(name = "invite", description = "Add the bot to your account or server.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def inviteBot(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = "Invite", description="Use this invite to add the bot to your account or server!", color=Color.green())
        embed.add_field(name = "Invite", value=f"https://titaniumbot.me/invite")

        view = View()
        view.add_item(discord.ui.Button(label="Add Bot", style=discord.ButtonStyle.url, url="https://discord.com/oauth2/authorize?client_id=1222612840146407484"))
        
        await interaction.followup.send(embed = embed, view=view, ephemeral=ephemeral)

    # Info command
    @botGroup.command(name = "info", description = "Info about the bot.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def info(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = "Titanium", description = "Hi, I'm Titanium! I'm a multi-purpose, open source Discord bot created by Restart (<@563372552643149825>). I use slash commands - use `/` to see all of my commands!", color = Color.green())
        embed.add_field(name = "GitHub", value = "You can also find me on GitHub - this is the place to go if you have found a bug or have a feature suggestion! Just submit an issue and I'll take a look. You can also add a star to show some love to the project. It's free and helps me a lot! https://github.com/restartb/titanium")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        repo = pygit2.Repository('.git')
        remote = repo.remotes["origin"]
        remote.fetch()

        # Get local HEAD commit
        local_head = repo.head.target

        # Get current branch name
        branch_name = repo.head.shorthand

        # Get remote HEAD for current branch
        remote_ref = f"refs/remotes/origin/{branch_name}"
        remote_head = repo.references[remote_ref].target

        # Convert to short hashes
        local_short = str(local_head)[:7]
        remote_short = str(remote_head)[:7]
        synced = local_head == remote_head

        embed.add_field(name = "Current Version", value = (f':white_check_mark: Up to date ({local_short})' if synced else f':x: Out of date ({local_short}, latest: {remote_short})'), inline = False)
        
        view = View()
        view.add_item(discord.ui.Button(label="GitHub", style=discord.ButtonStyle.url, url="https://github.com/restartb/titanium"))
        
        await interaction.followup.send(embed = embed, ephemeral=ephemeral, view=view)

    # Host Info command
    @botGroup.command(name = "host-info", description = "Info about the bot host.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def host_info(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = "Loading...", description=f"{self.bot.options['loading-emoji']} Getting info...", color = Color.random())
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        
        embed = discord.Embed(title = "Host Info", color=Color.random())

        sec = timedelta(seconds=int(time.monotonic()))
        d = datetime.datetime(1,1,1) + sec

        sysinfo = cpuinfo.get_cpu_info()

        embed.add_field(name = "Python Version", value = sysinfo['python_version'])
        embed.add_field(name = "System Uptime", value = ("%d:%d:%d:%d" % (d.day-1, d.hour, d.minute, d.second)))
        embed.add_field(name = "Operating System", value = f"{platform.system()} {platform.release()}")
        embed.add_field(name = "CPU Name", value = sysinfo['brand_raw'])
        embed.add_field(name = "CPU Usage", value = f"{psutil.cpu_percent()}%")
        embed.add_field(name = "RAM Usage", value = f"{psutil.virtual_memory().percent}%")
        
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

        await interaction.edit_original_response(embed = embed)

async def setup(bot):
    await bot.add_cog(BotUtils(bot))