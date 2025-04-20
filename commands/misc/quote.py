import asyncio
import os
import re
from io import BytesIO
from textwrap import shorten, wrap

import aiohttp
import discord
import pillow_avif  # noqa: F401
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pilmoji import Pilmoji


# Create quote image function
async def create_quote_image(
    user: discord.User,
    content: str,
    output_format: str,
    light_mode: bool = False,
    bw_mode: bool = False,
    custom_quote: bool = False,
    custom_quote_user: discord.User = None,
) -> BytesIO:
    # Get PFP, store in memory
    async with aiohttp.ClientSession() as session:
        async with session.get(user.display_avatar.url) as request:
            pfp_data = BytesIO()

            async for chunk in request.content.iter_chunked(10):
                pfp_data.write(chunk)

            pfp_data.seek(0)  # Reset buffer position to start

    # Run in thread to avoid blocking
    return await asyncio.to_thread(
        _create_quote_image_sync,
        user,
        pfp_data,
        content,
        output_format,
        light_mode,
        bw_mode,
        custom_quote,
        custom_quote_user,
    )


# Create quote image - sync function helper function
def _create_quote_image_sync(
    user: discord.User,
    pfp_data: BytesIO,
    content: str,
    output_format: str,
    light_mode: bool = False,
    bw_mode: bool = False,
    custom_quote: bool = False,
    custom_quote_user: discord.User = None,
) -> BytesIO:
    image_data = BytesIO()

    # Create image
    with Image.new("RGB", (1200, 600), ("white" if light_mode else "black")) as img:
        with Image.open(pfp_data) as pfp:
            if pfp.size[0] > 600 or pfp.size[1] > 600:
                pfp.thumbnail((600, 600))
            else:
                pfp = ImageOps.contain(pfp, (600, 600))

            if bw_mode:
                pfp = pfp.convert("L")

            mask = Image.linear_gradient("L").rotate(-90).resize((600, 600))
            img.paste(pfp, (0, 0), mask)

        draw = ImageDraw.Draw(img)

        EMOJI_REGEX = r"(<a?:\w+:\d{17,20}>)"
        placeholder = "\ufffc"  # Unicode replacement character

        # Get message content, remove any replacement characters from the user
        raw = content
        raw = raw.replace(placeholder, "\ue000")

        # Get custom Discord emojis in message
        emojis = re.findall(EMOJI_REGEX, raw)

        # Swap emojis with placeholder character
        for e in emojis:
            raw = raw.replace(e, placeholder, 1)

        # Calculate optimal font size and wrapping based on message length
        if len(raw) < 120:  # Large text
            font_size = 40

            # Shorten and wrap text
            wrapped = wrap(shorten(raw, 120, placeholder="..."), 20)
        else:  # Smaller text
            font_size = 35

            # Shorten and wrap text
            wrapped = wrap(shorten(raw, 180, placeholder="..."), 30)

        # Go through each line, replace placeholder with emoji
        processed_lines = []
        emoji_iter = iter(emojis)

        for line in wrapped:
            new_line = []
            for char in line:
                if char == placeholder:  # Placeholder found
                    try:
                        new_line.append(next(emoji_iter))
                    except StopIteration:  # Out of emojis
                        new_line.append(char)
                else:
                    new_line.append(char)
            processed_lines.append("".join(new_line))

        # Join lines, add new lines
        text = "\n".join(processed_lines) + "\n"

        with Pilmoji(img) as pilmoji:
            # Set regular Figtree font
            quote_font = ImageFont.truetype(
                os.path.join("content", "fonts", "Figtree-Medium.ttf"), font_size
            )

            # Get text width and height
            quote_width, quote_height = pilmoji.getsize(
                text=text, font=quote_font, spacing=20
            )

            # Calculate x and y position
            quote_x = ((600 - quote_width) // 2) + 600
            quote_y = (600 - quote_height) // 2

            # Draw quote text
            pilmoji.text(
                text=text,
                xy=(quote_x, quote_y),
                fill=("black" if light_mode else "white"),
                font=quote_font,
                align="center",
                spacing=20,
            )

            # Author text
            text = f"- @{user.name}"

            # Set bold Figtree font
            displayname_font = ImageFont.truetype(
                os.path.join("content", "fonts", "Figtree-Bold.ttf"), 30
            )

            # Get bounding box of text, get width
            displayname_width, displayname_height = pilmoji.getsize(
                text=text, font=displayname_font
            )

            # Calculate x and y position
            displayname_x = ((600 - displayname_width) // 2) + 600
            displayname_y = quote_y + 20 + quote_height

            # Draw text
            pilmoji.text(
                text=text,
                xy=(displayname_x, displayname_y),
                fill="gray",
                font=displayname_font,
                align="center",
            )

        # Footer text
        text = (
            "https://titaniumbot.me"
            if not custom_quote
            else f"Custom Quote by @{custom_quote_user.name}\nhttps://titaniumbot.me"
        )

        # Set bold Figtree font
        footer_font = ImageFont.truetype(
            os.path.join("content", "fonts", "Figtree-Bold.ttf"), 20
        )

        # Get bounding box of bottom text, calculate width and X position
        footer_box = draw.textbbox(
            text=text, xy=(0, 0), font=footer_font, align="center"
        )
        footer_width = footer_box[2] - footer_box[0]
        footer_height = footer_box[3] - footer_box[1]

        footer_x = ((600 - footer_width) // 2) + 600

        print(footer_height)

        # Draw bottom text
        draw.text(
            text=text,
            xy=(footer_x, (527 if custom_quote else 550)),
            fill=("red" if custom_quote else ("black" if light_mode else "white")),
            font=footer_font,
            align="center",
        )

        if output_format == "GIF" or output_format == "PNG":
            # Save image
            img.save(image_data, format=output_format)
        elif output_format == "AVIF":
            # Save image to AVIF
            img.save(
                image_data,
                format="AVIF",
                append_images=[img],
                save_all=True,
                duration=500,
                loop=0,
            )

        image_data.seek(0)
        return image_data


# Quotes view
class QuoteView(View):
    def __init__(
        self,
        user_id: int,
        content: str,
        output_format: str,
        og_msg: str = None,
        light_mode: bool = False,
        bw_mode: bool = False,
        custom_quote: bool = False,
        custom_quote_user_id: int = None,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.user_id = user_id
        self.content = content
        self.output_format = output_format
        self.og_msg = og_msg
        self.light_mode = light_mode
        self.bw_mode = bw_mode
        self.custom_quote = custom_quote
        self.custom_quote_user_id = custom_quote_user_id

        for child in self.children:
            if child.custom_id == "theme":
                if light_mode:
                    child.label = "Dark Mode"
                    child.emoji = "🌙"
                else:
                    child.label = "Light Mode"
                    child.emoji = "☀️"
            elif child.custom_id == "bw":
                if bw_mode:
                    child.label = "Colour"
                    child.emoji = "🎨"
                else:
                    child.label = "Black & White"
                    child.emoji = "⚫"

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, custom_id="theme")
    async def theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        # Try to get member if available
        user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)
            
            if user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the user. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return
        
        custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
        if custom_quote_user is None:
            embed = discord.Embed(
                title="Error",
                description="Couldn't find the user. Please try again later.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return

        image_data = await create_quote_image(
            user=user,
            content=self.content,
            output_format=self.output_format,
            light_mode=not self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
        )

        file = discord.File(
            fp=image_data,
            filename="titanium_quote.png",
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            output_format=self.output_format,
            og_msg=self.og_msg,
            light_mode=not self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        await interaction.edit_original_response(
            attachments=[file],
            view=view,
        )

        embed = discord.Embed(
            title="Done!",
            color=discord.Color.green(),
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, custom_id="bw")
    async def bw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        # Try to get member if available
        user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)

            if user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the user. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return

        custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
        if custom_quote_user is None:
            embed = discord.Embed(
                title="Error",
                description="Couldn't find the user. Please try again later.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return
        
        image_data = await create_quote_image(
            user=user,
            content=self.content,
            output_format=self.output_format,
            light_mode=self.light_mode,
            bw_mode=not self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
        )

        file = discord.File(
            fp=image_data,
            filename="titanium_quote.png",
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            output_format=self.output_format,
            og_msg=self.og_msg,
            light_mode=self.light_mode,
            bw_mode=not self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        await interaction.edit_original_response(
            attachments=[file],
            view=view,
        )

        embed = discord.Embed(
            title="Done!",
            color=discord.Color.green(),
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(
        label="", emoji="🔄", style=discord.ButtonStyle.gray, custom_id="reload"
    )
    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        # Try to get member if available
        user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)

            if user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the user. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return

        custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
        if custom_quote_user is None:
            embed = discord.Embed(
                title="Error",
                description="Couldn't find the user. Please try again later.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return
        
        image_data = await create_quote_image(
            user=user,
            content=self.content,
            output_format=self.output_format,
            light_mode=self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
        )

        file = discord.File(
            fp=image_data,
            filename="titanium_quote.png",
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            output_format=self.output_format,
            og_msg=self.og_msg,
            light_mode=self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        await interaction.edit_original_response(
            attachments=[file],
            view=view,
        )

        embed = discord.Embed(
            title="Done!",
            color=discord.Color.green(),
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    @discord.ui.button(
        label="", emoji="🗑️", style=discord.ButtonStyle.red, custom_id="delete"
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id == self.user_id:
            await interaction.delete_original_response()

            embed = discord.Embed(
                title="Done!",
                color=discord.Color.green(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="You cannot delete this quote, as you are not the original author.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )


class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Quote option
        self.quote_ctx = app_commands.ContextMenu(
            name="Quote This",
            callback=self.quote_callback,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(
                guild=True, user=True
            ),
        )

        self.bot.tree.add_command(self.quote_ctx)

    async def quote_callback(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        await interaction.response.defer()

        if message.clean_content == "":
            embed = discord.Embed(
                title="Error",
                description="Nothing to quote, this message is empty.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
            )

            return

        image_data = await create_quote_image(
            user=message.author,
            content=message.content,
            output_format="PNG",
        )

        file = discord.File(
            fp=image_data,
            filename="titanium_quote.png",
        )

        view = QuoteView(
            user_id=message.author.id,
            content=message.content,
            output_format="PNG",
            og_msg=message.jump_url,
            light_mode=False,
            bw_mode=False,
            custom_quote=False,
        )
        view.add_item(
            discord.ui.Button(
                label="Jump to Message",
                style=discord.ButtonStyle.link,
                url=message.jump_url,
            )
        )

        await interaction.followup.send(file=file, view=view)

    @app_commands.command(
        name="quote",
        description="Create a quote image. To quote messages, right click the message, click apps, then Quote This.",
    )
    @app_commands.describe(
        user="The user to quote.",
        content="The content to quote. To quote messages, right click the message, click apps, then Quote This.",
        format="Optional: the format to use. Defaults to PNG.",
        light_mode="Optional: whether to start with light mode. Defaults to false.",
        bw_mode="Optional: whether to start with black and white mode. Defaults to false.",
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(
                name=".png (can't be favourited, very good quality)",
                value="PNG",
            ),
            app_commands.Choice(
                name=".gif (can be favourited, bad quality, best compatibility)",
                value="GIF",
            ),
            app_commands.Choice(
                name=".avif (can be favourited, very good quality)",
                value="AVIF",
            ),
        ],
    )
    async def custom_quote(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        content: str,
        format: app_commands.Choice[str] = "",
        light_mode: bool = False,
        bw_mode: bool = False,
    ):
        await interaction.response.defer()

        if format == "":
            format = app_commands.Choice(
                name=".png (can't be favourited, very good quality)",
                value="PNG",
            )

        image_data = await create_quote_image(
            user=user,
            content=content,
            output_format=format.value,
            light_mode=light_mode,
            bw_mode=bw_mode,
            custom_quote=True,
            custom_quote_user=interaction.user
        )

        file = discord.File(
            fp=image_data,
            filename=f"titanium_quote.{format.value.lower()}",
        )

        view = QuoteView(
            user_id=user.id,
            content=content,
            output_format=format.value,
            light_mode=light_mode,
            bw_mode=bw_mode,
            custom_quote=True,
            custom_quote_user_id=interaction.user.id
        )

        await interaction.followup.send(file=file, view=view)


async def setup(bot):
    await bot.add_cog(Quotes(bot))
