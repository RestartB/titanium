import random
import string
import os

import discord
from discord import Color, app_commands
from discord.ext import commands
from PIL import Image


class image(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    imageGroup = app_commands.Group(name="image", description="Manipulate images.", allowed_contexts=context, allowed_installs=installs)
    
    # Image Resize command
    @imageGroup.command(name = "resize", description = "Resize an image.")
    @app_commands.describe(target_x = "Set a target width for the image. Defaults to the original length.")
    @app_commands.describe(target_y = "Set a target height for the image. Defaults to the original length.")
    @app_commands.describe(scale = "Scale the resolution by a certain amount. Overrides target_x and target_y if set.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 20)
    async def resizeImage(self, interaction: discord.Interaction, file: discord.Attachment, scale: float = None, target_x: int = None, target_y: int = None, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        if file.content_type.split('/')[0] == "image" and file.content_type.split('/')[1] != "gif" and file.content_type.split('/')[1] != "apng": # Check if file is a static image
            if file.size < 20000000: # 20MB file limit
                if ((scale is not None) or (target_x is not None) or (target_y is not None)): # If scale or target_x or target_y are set
                    if scale is not None: # If scale is set
                        # Set target_x and target_y to scaled image size
                        target_x = int(file.width * scale)
                        target_y = int(file.height * scale)
                    else: # If scale is not set
                        # Set target_x and target_y to original image size if not set
                        target_x = target_x if target_x is not None else file.width
                        target_y = target_y if target_y is not None else file.height
                    
                    if target_x > 4000 or target_y > 4000: # Check if image is too large
                        embed = discord.Embed(title="Error", description=f"The result of this operation is too large. Please ensure it is smaller than 4000x4000. (current size: {target_x}x{target_y})", color=Color.red())
                        embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                        
                        await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                        return
                    
                    try:
                        # Generate random filename
                        letters = string.ascii_lowercase
                        filename = ''.join(random.choice(letters) for i in range(8))
                        
                        # Save file to /tmp
                        await file.save(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
                        
                        # Open image
                        with Image.open(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")) as im:
                            # Resize image
                            resizedImage = im.resize((int(target_x), int(target_y)))
                            
                            # Save resized image
                            resizedImage.save(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))
                            newSize = resizedImage.size

                            fileSize = os.path.getsize(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))
                            
                            if fileSize > 20000000: # Check if image is too large
                                embed = discord.Embed(title="Error", description=f"The result of this operation is too large. Please ensure it is smaller than 20MB. (current size: {fileSize / 6})", color=Color.red())
                                embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                                
                                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                                return
                            
                            # Send resized image
                            embed = discord.Embed(title="Image Resized", description=f"Image resized to {newSize[0]}x{newSize[1]}.", color=Color.green())
                            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)

                            fileNew = discord.File(fp=os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"), filename="image.png")
                            embed.set_image(url="attachment://image.png")
                            
                            await interaction.followup.send(embed=embed, file=fileNew, ephemeral=ephemeral)

                        # Delete temporary files
                        os.remove(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
                        os.remove(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))
                    except Exception as e:
                        try:
                            # Delete temporary files
                            os.remove(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
                            os.remove(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))
                        except Exception:
                            pass
                        
                        raise e
                else: # Check if both scale and target_x or target_y are set
                    embed = discord.Embed(title="Error", description=f"Please provide a scale, target width or target height.", color=Color.red())
                    embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                    
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else: # If file is too large
                embed = discord.Embed(title="Error", description=f"Your file is too large. Please ensure it is smaller than 20MB.", color=Color.red())
                embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else: # If file is not a static image
            embed = discord.Embed(title="Error", description=f"Your file is not a static image.", color=Color.red())
            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    
    # Image to GIF command
    @imageGroup.command(name = "to-gif", description = "Convert an image to GIF.")
    @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    @app_commands.checks.cooldown(1, 10)
    async def gifImage(self, interaction: discord.Interaction, file: discord.Attachment, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)
        
        if file.content_type.split('/')[0] == "image" and file.content_type.split('/')[1] != "gif" and file.content_type.split('/')[1] != "apng": # Check if file is a static image
            if file.size < 20000000: # 20MB file limit
                while True:
                    # Generate random filename
                    letters = string.ascii_lowercase
                    filename = ''.join(random.choice(letters) for i in range(8))

                    if not os.path.exists(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")):
                        break
                
                # Save file to /tmp
                await file.save(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
                
                # Open image
                with Image.open(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}")) as im:
                    # Convert image to GIF
                    im.save(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))

                    # Send resized image
                    embed = discord.Embed(title="Image Converted", description=f"Image converted to GIF.", color=Color.green())
                    embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)

                    file = discord.File(fp=os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"), filename="image.gif")
                    embed.set_image(url="attachment://image.gif")
                    
                    await interaction.followup.send(embed=embed, file=file, ephemeral=ephemeral)

                # Delete temporary files
                os.remove(os.path.join("tmp", f"{filename}_processed.{file.content_type.split('/')[-1]}"))
                os.remove(os.path.join("tmp", f"{filename}.{file.content_type.split('/')[-1]}"))
            else: # If file is too large
                embed = discord.Embed(title="Error", description=f"Your file is too large. Please ensure it is smaller than 20MB.", color=Color.red())
                embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else: # If file is not a static image
            embed = discord.Embed(title="Error", description=f"Your file is not a static image.", color=Color.red())
            embed.set_footer(text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    
    # # Image Caption command
    # @imageGroup.command(name = "caption", description = "Add a caption to an image.")
    # @app_commands.describe(file = "Your target image.")
    # @app_commands.describe(caption = "Your caption.")
    # @app_commands.describe(ephemeral = "Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.")
    # @app_commands.checks.cooldown(1, 20)
    # async def bounceImage(self, interaction: discord.Interaction, file: discord.Attachment, caption: str, ephemeral: bool = False):
    #     await interaction.response.defer(ephemeral=ephemeral)
        
    #     if file.content_type.split('/')[0] == "image" and file.content_type.split('/')[1] != "gif" and file.content_type.split('/')[1] != "apng":
    #         if file.size < 20000000:
    #             # Generate random filename
    #             letters = string.ascii_lowercase
    #             filename = ''.join(random.choice(letters) for i in range(8))
                
    #             # Save file to /tmp
    #             await file.save(f"/tmp/{filename}.{file.content_type.split('/')[-1]}")
    #             im = Image.open(f"/tmp/{filename}.{file.content_type.split('/')[-1]}")
                
    #             # Create a new image with a white box above
    #             width, height = im.size
    #             new_height = height + 50  # Adjust the height for the caption box
    #             new_im = Image.new("RGBA", (width, new_height), (255, 255, 255, 0))

    #             # Draw the white box and caption text
    #             draw = ImageDraw.Draw(new_im)
    #             draw.rectangle([(0, 0), (width, 50)], fill="white")

    #             # Load font with specified size
    #             font_size = 30  # Change this value to adjust the font size
    #             font = ImageFont.truetype(os.path.join("content", "futura.ttf"), font_size)

    #             # Calculate text size and position
    #             text_width, text_height = draw.textlength(caption, font=font), 30
    #             text_x = (width - text_width) // 2
    #             text_y = (50 - text_height) // 2

    #             # Draw the caption text
    #             draw.text((text_x, text_y), caption, fill="black", font=font)

    #             # Paste the original image below the white box
    #             new_im.paste(im, (0, 50))

    #             # Save the new image to a BytesIO object
    #             img_data = io.BytesIO()
    #             new_im.save(img_data, format="PNG")
    #             img_data.seek(0)
                
    #             await interaction.followup.send(file=discord.File(img_data, "captioned_image.png"), ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(image(bot))