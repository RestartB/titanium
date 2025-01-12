import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class UserUtils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    userGroup = app_commands.Group(name="user", description="User related commands.", allowed_contexts=context, allowed_installs=installs)

    # Server Info command
    @userGroup.command(name = "info", description = "Get info about a user.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def server_info(self, interaction: discord.Interaction, user: discord.User, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        if interaction.guild is not None:
            try:
                member = interaction.guild.get_member(user.id)
                userInstalled = False

                if member == None:
                    member = user
                    inGuild = False
                else:
                    inGuild = True
            except Exception:
                member = user
                inGuild = False
        else:
            member = user
            userInstalled = True
            inGuild = False
        
        embed = discord.Embed(title = f"User Info", color = Color.random())
        embed.set_author(name=f"{member.display_name} (@{member.name})", icon_url=member.display_avatar.url)

        creationDate = int(member.created_at.timestamp())
        joinDate = (int(member.joined_at.timestamp()) if inGuild else None)
        
        embed.add_field(name = "ID", value = member.id)
        
        # Other info
        embed.add_field(name = "Joined Discord", value = f"<t:{creationDate}:R> (<t:{creationDate}:f>)")
        (embed.add_field(name = "Joined Server", value = f"<t:{joinDate}:R> (<t:{joinDate}:f>)") if inGuild else None)

        if userInstalled:
            embed.description = ""
            embed.set_footer(text = f"@{interaction.user.name} - add Titanium to the server for more info.", icon_url = interaction.user.display_avatar.url)
        elif inGuild:
            roles = []
            
            for role in member.roles:
                roles.append(role.mention)
            
            embed.add_field(name = "Roles", value = ", ".join(roles))

            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        elif not inGuild:
            embed.set_footer(text = f"@{interaction.user.name} - target is not in the server, showing limited info.", icon_url = interaction.user.display_avatar.url)
        
        embed.set_thumbnail(url = member.display_avatar.url)
        
        view = View()
        view.add_item(discord.ui.Button(label="User URL", style=discord.ButtonStyle.url, url=f"https://discord.com/users/{user.id}", row = 0))
        view.add_item(discord.ui.Button(label="Open PFP in Browser", style=discord.ButtonStyle.url, url=user.display_avatar.url, row = 0))
        
        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    # PFP command
    @userGroup.command(name = "pfp", description = "Show a user's PFP.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user = "The target user.")  
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    async def pfp(self, interaction: discord.Interaction, user: discord.User, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        embed = discord.Embed(title = "PFP", color = (user.accent_color if user.accent_color != None else Color.random()))
        embed.set_image(url = user.display_avatar.url)
        embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

        view = View()
        view.add_item(discord.ui.Button(label="Open in Browser", style=discord.ButtonStyle.url, url=user.display_avatar.url, row = 0))
        
        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(UserUtils(bot))