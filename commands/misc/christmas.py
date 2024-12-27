# pylint: disable=no-member

import os
import random
import string

import discord
import discord.ext
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View
from PIL import Image


def invert(num: int):
    if num > 0:
        return -num
    elif num < 0:
        return abs(num)
    else:
        return 0

class Christmas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot: commands.Bot
    
    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    christmasGroup = app_commands.Group(name="christmas", description="Christmas related commands.", allowed_contexts=context, allowed_installs=installs)
    
    # Christmas PFP command
    @christmasGroup.command(name = "pfp", description = "Add a Christmas hat to a user's PFP.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user = "The target user.")
    @app_commands.describe(hat = "Optional: whether to add a christmas hat. Defaults to true.")
    @app_commands.describe(snow = "Optional: whether to add snow. Defaults to true.")
    @app_commands.describe(hat_size = "Optional: the size of the hat on the user's head when enabled. Defaults to normal.")
    @app_commands.describe(position = "Optional: the position of the hat on the user's head when enabled. Defaults to top middle.")
    @app_commands.describe(x_offset = "Optional: manual x (horizontal) position adjustment (-128 to 128). Defaults to 0.")
    @app_commands.describe(y_offset = "Optional: manual y (vertical) position adjustment (-128 to 128). Defaults to 0.")
    @app_commands.describe(rotation = "Optional: rotation angle in degrees (-180 to 180). Defaults to 0.")
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
    async def christmasPFP(self, interaction: discord.Interaction, 
                   user: discord.User, 
                   hat: bool = True,
                   snow: bool = True,
                   hat_size: app_commands.Choice[int] = None,
                   position: app_commands.Choice[str] = None,
                   x_offset: app_commands.Range[int, -128, 128] = 0,
                   y_offset: app_commands.Range[int, -128, 128] = 0, 
                   rotation: app_commands.Range[int, -180, 180] = 0,
                   ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        try:
            # Validate ranges
            x_offset = max(-128, min(128, x_offset))
            y_offset = max(-128, min(128, y_offset))
            rotation = max(-180, min(180, rotation))
            
            if user is None:
                user = interaction.user
            
            if hat_size is None:
                hat_size = app_commands.Choice(name="Normal", value=4)
            
            if position is None:
                position = app_commands.Choice(name="Top Middle", value="topmiddle")

            # Generate random filename
            letters = string.ascii_lowercase
            filename = ''.join(random.choice(letters) for i in range(8))

            # Get user PFP
            await user.display_avatar.save(os.path.join("tmp", f"{filename}.png"))
            
            with Image.open(os.path.join("tmp", f"{filename}.png")) as img:
                # Resize to 256px x 256px while maintianing aspect ratio
                width = 256
                height = width * img.height // img.width 

                img.thumbnail((width, height), Image.Resampling.LANCZOS)
                
                # Christmas hat
                if hat:
                    with Image.open(os.path.join("content", "hat.png")) as hatImg:
                        # Resize the hat to fit the head - maintain aspect ratio
                        new_hat_width = hatImg.width // hat_size.value
                        new_hat_height = hatImg.height // hat_size.value
                        hatImg = hatImg.resize((new_hat_width, new_hat_height), Image.Resampling.LANCZOS)

                        # Rotate if needed
                        if rotation != 0:
                            hatImg = hatImg.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

                        # Calculate positions based on hat size
                        positions = {
                            "topleft": (0, 0),
                            "topmiddle": ((img.width - new_hat_width) // 2, 0),
                            "topright": (img.width - new_hat_width, 0),
                            "bottomleft": (0, img.height - new_hat_height),
                            "bottommiddle": ((img.width - new_hat_width) // 2, img.height - new_hat_height),
                            "bottomright": (img.width - new_hat_width, img.height - new_hat_height)
                        }

                        # Place hat at calculated position
                        base_x, base_y = positions[position.value]

                        # Adjust vertical position for large hat
                        if position.value.startswith("top") and hat_size.value == 2:
                            base_y = base_y + 80

                        # Get base position and apply offsets
                        base_x, base_y = positions[position.value]
                        final_x = base_x + x_offset
                        final_y = base_y + invert(y_offset)
                        
                        img.paste(hatImg, (final_x, final_y), hatImg)
                
                # Snow overlay
                if snow:
                    with Image.open(os.path.join("content", "snow.png")) as snow: 
                        img.paste(snow, (0, 0), snow)

                # Save image
                img.save(os.path.join('tmp', f'{filename}-processed.png'))
                
            # Create embed, add attachment
            embed = discord.Embed(title = "Christmas PFP", color = (user.accent_color if user.accent_color != None else Color.random()))
            embed.set_image(url = "attachment://image.png")
            embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

            fileProcessed = discord.File(fp=os.path.join("tmp", f"{filename}-processed.png"), filename=f"image.png")
            
            # Send Embed
            msg = await interaction.followup.send(embed=embed, file=fileProcessed, ephemeral=ephemeral, wait=True)

            # Get image URL
            view = View()
            view.add_item(discord.ui.Button(label="Open in Browser", style=discord.ButtonStyle.url, url=msg.embeds[0].image.url, row = 0))

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
    
    # Christmas Image command
    @christmasGroup.command(name = "image", description = "(beta) Add a Christmas hat and effects to an image.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(file = "The image to edit.")
    @app_commands.describe(hat = "Optional: whether to add a christmas hat. Defaults to true.")
    @app_commands.describe(snow = "Optional: whether to add snow. Defaults to true.")
    @app_commands.describe(hat_width = "Optional: the width in px of the christmas hat when enabled. Defaults to half of image length.")
    @app_commands.describe(position = "Optional: the position of the hat on the user's head when enabled. Defaults to top middle.")
    @app_commands.describe(x_offset = "Optional: manual x (horizontal) position adjustment (-128 to 128). Defaults to 0.")
    @app_commands.describe(y_offset = "Optional: manual y (vertical) position adjustment (-128 to 128). Defaults to 0.")
    @app_commands.describe(rotation = "Optional: rotation angle in degrees (-180 to 180). Defaults to 0.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.")
    @app_commands.choices(position=[
            app_commands.Choice(name="Top Left", value="topleft"),
            app_commands.Choice(name="Top Middle", value="topmiddle"),
            app_commands.Choice(name="Top Right", value="topright"),
            app_commands.Choice(name="Middle Left", value="middleleft"),
            app_commands.Choice(name="Middle", value="middle"),
            app_commands.Choice(name="Middle Right", value="middleright"),
            app_commands.Choice(name="Bottom Left", value="bottomleft"),
            app_commands.Choice(name="Bottom Middle", value="bottommiddle"),
            app_commands.Choice(name="Bottom Right", value="bottomright"),
            ])
    async def christmasImage(self, interaction: discord.Interaction, 
                   file: discord.Attachment, 
                   hat: bool = True,
                   snow: bool = True,
                   hat_width: app_commands.Range[int, 10, 1000] = 0,
                   position: app_commands.Choice[str] = None,
                   x_offset: int = 0,
                   y_offset: int = 0, 
                   rotation: app_commands.Range[int, -180, 180] = 0,
                   ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        try:
            if position is None:
                position = app_commands.Choice(name="Top Middle", value="topmiddle")

            if file.content_type.split('/')[0] == "image" and file.content_type.split('/')[1] != "gif" and file.content_type.split('/')[1] != "apng": # Check if file is a static image
                if file.size < 20000000: # 20MB file limit
                    while True:
                        # Generate random filename
                        letters = string.ascii_lowercase
                        filename = ''.join(random.choice(letters) for i in range(8))

                        if not os.path.exists(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")):
                            break

            # Get user PFP
            await file.save(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
            
            with Image.open(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")) as img:
                # Christmas hat
                if hat:
                    with Image.open(os.path.join("content", "hat.png")) as hatImg:
                        # Set width to half of image width if not specified
                        if hat_width == 0:
                            hat_width = img.width // 2
                        
                        # Resize to new size while maintianing aspect ratio
                        new_hat_width = hat_width
                        new_hat_height = new_hat_width * hatImg.height // hatImg.width
                        hatImg = hatImg.resize((new_hat_width, new_hat_height), Image.Resampling.LANCZOS)

                        # Rotate if needed
                        if rotation != 0:
                            hatImg = hatImg.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

                        # Calculate positions based on hat size
                        positions = {
                            "topleft": (0, 0),
                            "topmiddle": ((img.width - new_hat_width) // 2, 0),
                            "topright": (img.width - new_hat_width, 0),
                            "middleleft": (0, (img.height - new_hat_height) // 2),
                            "middle": ((img.width - new_hat_width) // 2, (img.height - new_hat_height) // 2),
                            "middleright": (img.width - new_hat_width, (img.height - new_hat_height) // 2),
                            "bottomleft": (0, img.height - new_hat_height),
                            "bottommiddle": ((img.width - new_hat_width) // 2, img.height - new_hat_height),
                            "bottomright": (img.width - new_hat_width, img.height - new_hat_height)
                        }

                        # Place hat at calculated position
                        base_x, base_y = positions[position.value]

                        # Get base position and apply offsets
                        base_x, base_y = positions[position.value]
                        final_x = base_x + x_offset
                        final_y = base_y + invert(y_offset)
                        
                        img.paste(hatImg, (final_x, final_y), hatImg)
                
                # Snow overlay
                if snow:
                    with Image.open(os.path.join("content", "snow.png")) as snowImg: 
                        # Create snow layer
                        snow_layer = Image.new("RGBA", img.size)

                        # Tile snow overlay over image
                        for x in range(0, img.width, snowImg.width):
                            for y in range(0, img.height, snowImg.height):
                                snow_layer.paste(snowImg, (x, y))

                        # Put snow layer on top of image
                        img.paste(snow_layer, (0, 0), snow_layer)

                # Save image
                img.save(os.path.join('tmp', f'{filename}-processed.{file.content_type.split('/')[-1]}'))
                
            # Create embed, add attachment
            embed = discord.Embed(title = "Christmas Image", color = Color.random())
            embed.set_image(url = f"attachment://image.{file.content_type.split('/')[-1]}")
            embed.set_footer(text = f"@{interaction.user.name}", icon_url = interaction.user.display_avatar.url)

            fileProcessed = discord.File(fp=os.path.join("tmp", f"{filename}-processed.{file.content_type.split('/')[-1]}"), filename=f"image.{file.content_type.split('/')[-1]}")
            
            # Send Embed
            msg = await interaction.followup.send(embed=embed, file=fileProcessed, ephemeral=ephemeral, wait=True)

            # Get image URL
            view = View()
            view.add_item(discord.ui.Button(label="Open in Browser", style=discord.ButtonStyle.url, url=msg.embeds[0].image.url, row = 0))

            await interaction.edit_original_response(view=view)

            # Delete temp files if they exist
            if os.path.exists(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")):
                os.remove(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
            
            if os.path.exists(os.path.join("tmp", f"{filename}-processed.{file.content_type.split('/')[-1]}")):
                os.remove(os.path.join("tmp", f"{filename}-processed.{file.content_type.split('/')[-1]}"))
        except Exception as e:
            # Delete temp files if they exist
            if os.path.exists(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")):
                os.remove(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
            
            if os.path.exists(os.path.join("tmp", f"{filename}-processed.{file.content_type.split('/')[-1]}")):
                os.remove(os.path.join("tmp", f"{filename}-processed.{file.content_type.split('/')[-1]}"))
            
            raise e

async def setup(bot):
    await bot.add_cog(Christmas(bot))