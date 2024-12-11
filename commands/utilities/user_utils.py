import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View

from PIL import Image
import string
import random
import os


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
        
        try:
            member = interaction.guild.get_member(user.id)

            if member == None:
                member = user
                inGuild = False
            else:
                inGuild = True
        except Exception:
            member = user
            inGuild = False
        
        embed = discord.Embed(title = f"User Info", color = Color.random())
        embed.set_author(name=f"{member.display_name} (@{member.name})", icon_url=member.display_avatar.url)

        creationDate = int(member.created_at.timestamp())
        joinDate = (int(member.joined_at.timestamp()) if inGuild else None)
        
        embed.add_field(name = "ID", value = member.id)
        
        # Other info
        embed.add_field(name = "Joined Discord", value = f"<t:{creationDate}:R> (<t:{creationDate}:f>)")
        (embed.add_field(name = "Joined Server", value = f"<t:{joinDate}:R> (<t:{joinDate}:f>)") if inGuild else None)

        if inGuild:
            roles = []
            
            for role in member.roles:
                roles.append(role.mention)
            
            embed.add_field(name = "Roles", value = ", ".join(roles))

            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)
        else:
            embed.set_footer(text = f"@{interaction.user.name} - Want more info? Add the bot to the server!", icon_url = interaction.user.display_avatar.url)
        
        embed.set_thumbnail(url = member.display_avatar.url)
        
        view = View()
        view.add_item(discord.ui.Button(label="User URL", style=discord.ButtonStyle.url, url=f"https://discord.com/users/{user.id}", row = 0))
        view.add_item(discord.ui.Button(label="Download PFP", style=discord.ButtonStyle.url, url=user.display_avatar.url, row = 0))
        
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
        embed.set_author(name=f"{user.name} (@{user.name})", icon_url=user.display_avatar.url)
        embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

        view = View()
        view.add_item(discord.ui.Button(label="Download PFP", style=discord.ButtonStyle.url, url=user.display_avatar.url, row = 0))
        
        # Send Embed
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    # Christmas PFP command
    @userGroup.command(name = "christmas", description = "Add a Christmas hat to a user's PFP.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user = "The target user.")
    @app_commands.describe(hat = "Optional: whether to add a christmas hat. Defaults to true.")
    @app_commands.describe(snow = "Optional: whether to add snow. Defaults to true.")
    @app_commands.describe(position = "Optional: the size of the hat on the user's head when enabled. Defaults to normal.")
    @app_commands.describe(position = "Optional: the position of the hat on the user's head when enabled. Defaults to top middle.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    @app_commands.choices(hat_size=[
            app_commands.Choice(name="Small", value=6),
            app_commands.Choice(name="Normal", value=4),
            app_commands.Choice(name="Large", value=2),
            ])
    @app_commands.choices(position=[
            app_commands.Choice(name="Top Left", value="topleft"),
            app_commands.Choice(name="Top Middle", value="topmiddle"),
            app_commands.Choice(name="Top Right", value="topright"),
            app_commands.Choice(name="Bottom Left", value="bottomleft"),
            app_commands.Choice(name="Bottom Middle", value="bottommiddle"),
            app_commands.Choice(name="Bottom Right", value="bottomright"),
            ])
    async def christmas(self, interaction: discord.Interaction, user: discord.User, hat: bool = True, snow: bool = True, size: app_commands.Choice[str] = None, position: app_commands.Choice[str] = None, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        try:
            if user is None:
                user = interaction.user
            
            if size is None:
                size = app_commands.Choice(name="Normal", value=4)
            
            if position is None:
                position = app_commands.Choice(name="Top Middle", value="topmiddle")

            # Generate random filename
            letters = string.ascii_lowercase
            filename = ''.join(random.choice(letters) for i in range(8))

            # Get user PFP
            await user.display_avatar.save(os.path.join("tmp", f"{filename}.png"))
            
            img = Image.open(os.path.join("tmp", f"{filename}.png"))

            # Resize to 256px x 256px while maintianing aspect ratio
            width = 256
            height = width * img.height // img.width 

            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # Christmas hat
            if hat:
                hatImg = Image.open(os.path.join("content", "hat.png"))

                # Resize the hat to fit the head - maintain aspect ratio
                hatImg = hatImg.resize((hatImg.width//int(size.value), hatImg.height//int(size.value)), Image.Resampling.LANCZOS)

                # Put hat on head in requested position
                if position.value == "topleft":
                    img.paste(hatImg, (0, 0), hatImg)
                elif position.value == "topmiddle":
                    img.paste(hatImg, (img.width//4, 0), hatImg)
                elif position.value == "topright":
                    img.paste(hatImg, (img.width//2, 0), hatImg)
                elif position.value == "bottomleft":
                    img.paste(hatImg, (0, img.height//2), hatImg)
                elif position.value == "bottommiddle":
                    img.paste(hatImg, (img.width//4, img.height//2), hatImg)
                elif position.value == "bottomright":
                    img.paste(hatImg, (img.width//2, img.height//2), hatImg)
            
            # Snow overlay
            if snow:
                snow = Image.open(os.path.join("content", "snow.png"))
                img.paste(snow, (0, 0), snow)

            # Save image
            img.save(os.path.join('tmp', f'{filename}-processed.png'))
            
            # Create embed, add attachment
            embed = discord.Embed(title = "Christmas PFP", color = (user.accent_color if user.accent_color != None else Color.random()))
            embed.set_image(url = "attachment://image.png")
            embed.set_author(name=f"{user.name} (@{user.name})", icon_url=user.display_avatar.url)
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

            fileProcessed = discord.File(fp=os.path.join("tmp", f"{filename}-processed.png"), filename=f"image.png")
            
            # Send Embed
            msg = await interaction.followup.send(embed=embed, file=fileProcessed, ephemeral=ephemeral, wait=True)

            # Get image URL
            view = View()
            view.add_item(discord.ui.Button(label="Download PFP", style=discord.ButtonStyle.url, url=msg.embeds[0].image.url, row = 0))

            await interaction.edit_original_response(view=view)

            # Delete temp files if they exist
            if os.path.exists(os.path.join("tmp", f"{filename}.png")):
                os.remove(os.path.join("tmp", f"{filename}.png"))
            
            if os.path.exists(os.path.join("tmp", f"{filename}-processed.png")):
                os.remove(os.path.join("tmp", f"{filename}-processed.png"))
        except Exception as e:
            # Delete temp files if they exist
            if os.path.exists(os.path.join("tmp", f"{filename}.png")):
                os.remove(os.path.join("tmp", f"{filename}.png"))
            
            if os.path.exists(os.path.join("tmp", f"{filename}-processed.png")):
                os.remove(os.path.join("tmp", f"{filename}-processed.png"))
            
            raise e

async def setup(bot):
    await bot.add_cog(UserUtils(bot))