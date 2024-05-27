import discord
from discord import app_commands, Color
import discord.ext
from discord.ext import commands
from discord.ui import View

class server_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    serverGroup = app_commands.Group(name="server", description="Server related commands.")

    # Server Icon command
    @serverGroup.command(name = "icon", description = "Show the server's icon.")
    async def server_icon(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Send initial embed
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)

        # Handle no icon
        try:
            embed = discord.Embed(title = f"PFP - {interaction.guild.name}", color = Color.random())
            embed.set_image(url = interaction.guild.icon.url)
            embed.set_footer(text = f"Requested by {interaction.user.name} - right click or long press to save image", icon_url = interaction.user.avatar.url)

            # Send Embed
            await interaction.followup.send(embed = embed)
        except AttributeError:
            embed = discord.Embed(title = "Server has no icon!", color = Color.red())
            await interaction.edit_original_response(embed = embed, view = None)
        
    # Server Icon command
    @serverGroup.command(name = "info", description = "Get info about the server.")
    async def server_info(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Send initial embed
        embed = discord.Embed(title = "Loading...", color = Color.orange())
        embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
        await interaction.followup.send(embed = embed)
        
        try:
            memberCount = 0
            botCount = 0
            
            for member in interaction.guild.members:
                if member.bot == True:
                    botCount += 1
                else:
                    memberCount += 1
            
            embed = discord.Embed(title = f"{interaction.guild.name} - Info", color = Color.random())
            
            # Member counts
            embed.add_field(name = "Total Members", value = interaction.guild.member_count)
            embed.add_field(name = "People", value = memberCount, inline = True)
            embed.add_field(name = "Bots", value = botCount, inline = True)

            # Channel counts
            embed.add_field(name = "Text Channels", value = len(interaction.guild.text_channels))
            embed.add_field(name = "Voice Channels", value = len(interaction.guild.voice_channels))
            embed.add_field(name = "Categories", value = len(interaction.guild.categories))

            creationDate = interaction.guild.created_at
            
            # Other info
            embed.add_field(name = "Creation Date", value = f"{creationDate.day}/{creationDate.month}/{creationDate.year}")
            
            # Handle when owner can't be found
            try:
                embed.add_field(name = "Owner", value = interaction.guild.owner.mention)
            except AttributeError:
                embed.add_field(name = "Owner", value = "Unknown")
            
            embed.add_field(name = "Server ID", value = interaction.guild.id)
            
            view = View()
            
            # Skip button when there's no vanity invite
            try:
                if interaction.guild.vanity_url != None:
                    view.add_item(discord.ui.Button(style = discord.ButtonStyle.url, url = interaction.guild.vanity_url, label = "Vanity Invite"))
            except Exception:
                pass
            
            # Handle no icon
            try:
                embed.set_thumbnail(url = interaction.guild.icon.url)
            except AttributeError:
                pass
            
            embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
            
            # Send Embed
            await interaction.edit_original_response(embed = embed, view = view)
        except Exception:
            embed = discord.Embed(title = "Unexpected Error", description = "Please try again later or message <@563372552643149825> for assistance.", color = Color.red())
            await interaction.edit_original_response(embed = embed, view = None)
      
async def setup(bot):
    await bot.add_cog(server_utils(bot))