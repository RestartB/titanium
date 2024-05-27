import discord
from discord import app_commands, Color
import discord.ext
from discord.ext import commands

class bot_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    serverGroup = app_commands.Group(name="server", description="Server related commands.")

    # Server Icon command
    @serverGroup.command(name = "icon", description = "Show the server's icon.")
    async def server_icon(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # Idea: set embed colour to user's banner colour'
        embed = discord.Embed(title = f"PFP - {interaction.guild.name}", color = Color.random())
        embed.set_image(url = interaction.guild.icon.url)
        embed.set_footer(text = f"Requested by {interaction.user.name} - right click or long press to save image", icon_url = interaction.user.avatar.url)
        # Send Embed
        await interaction.followup.send(embed = embed)
    
    # Server Icon command
    @serverGroup.command(name = "info", description = "Get info about the server.")
    async def server_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Send initial embed
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        memberCount = 0
        botCount = 0
        
        for member in interaction.guild.member_count:
            if member.bot == True:
                botCount += 1
            else:
                memberCount += 1
        
        embed = discord.Embed(title = f"{interaction.guild.name} - Info", color = Color.random())
        
        # Member counts
        embed.add_field(name = "Total Members", value = interaction.guild.member_count, inline = True)
        embed.add_field(name = "People", value = memberCount, inline = True)
        embed.add_field(name = "Bots", value = botCount, inline = True)

        # Channel counts
        embed.add_field(name = "Text Channels", value = len(interaction.guild.text_channels), inline = False)
        embed.add_field(name = "Voice Channels", value = len(interaction.guild.voice_channels), inline = True)
        embed.add_field(name = "Categories", value = len(interaction.guild.categories))

        # Other info
        embed.add_field(name = "Creation Date", value = interaction.guild.created_at, inline = False)
        embed.add_field(name = "Owner", value = interaction.guild.owner.mention, inline = True)
        embed.add_field(name = "Server ID", value = interaction.guild.id, inline = True)
        
        view = View()
        
        # Skip button when there's no vanity invite
        try:
            view.add_item(discord.ui.Button(style = discord.ButtonStyle.url, url = interaction.guild.vanity_url, label = "Vanity Invite"))
        except Exception:
            pass
        
        embed.set_thumbnail(url = interaction.guild.icon.url)
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        
        # Send Embed
        await interaction.followup.send(embed = embed, view = view)