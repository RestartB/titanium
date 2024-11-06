import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class server_utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
    serverGroup = app_commands.Group(name="server", description="Server related commands.", allowed_contexts=context)

    # Server Icon command
    @serverGroup.command(name = "icon", description = "Show the server's icon.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def server_icon(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        # Handle no icon
        try:
            embed = discord.Embed(title = f"Server Icon - {interaction.guild.name}", color = Color.random())
            embed.set_image(url = interaction.guild.icon.url)
            embed.set_footer(text = f"@{interaction.user.name} - right click or long press to save image", icon_url = interaction.user.display_avatar.url)

            # Send Embed
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        except AttributeError:
            embed = discord.Embed(title = "Server has no icon!", color = Color.red())
            await interaction.followup.send(embed = embed, ephemeral=ephemeral)
        
    # Server Info command
    @serverGroup.command(name = "info", description = "Get info about the server.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def server_info(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        memberCount = 0
        botCount = 0
        
        for member in interaction.guild.members:
            if member.bot == True:
                botCount += 1
            else:
                memberCount += 1
        
        memberCount = f"{memberCount} ({round((memberCount / interaction.guild.member_count * 100), 1)}%)"
        botCount = f"{botCount} ({round((botCount / interaction.guild.member_count * 100), 1)}%)"
        
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
        
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        
        # Send Embed
        await interaction.followup.send(embed = embed, view = view, ephemeral=ephemeral)

    # Server Info command
    @serverGroup.command(name = "boosts", description = "Beta: get info about this server's boost stats.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def server_boost(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = f"{interaction.guild.name} - Info", color = Color.random())
        
        # Member counts
        embed.add_field(name = "Total Boosts", value = interaction.guild.premium_subscription_count)
        embed.add_field(name = "Level", value = f"Level {interaction.guild.premium_tier}", inline = True)
        #embed.add_field(name = "Boosts Needed for Next Level", value = memberCount, inline = True)

        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        
        # Send Embed
        await interaction.followup.send(embed = embed, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(server_utils(bot))