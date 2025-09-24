import asyncio
import html
import os
import re
from io import BytesIO
from typing import Sequence, Union

import discord
import jinja2
import pillow_avif  # noqa: F401
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from PIL import Image
from playwright.async_api import async_playwright
from wand.image import Image as WandImage


def _to_gif(
    image_data: BytesIO,
    mode: str,
) -> tuple[BytesIO, tuple[int, int]]:
    output_data = BytesIO()

    # Open image
    with Image.open(image_data) as im:
        if mode == "quality":
            with Image.open(image_data) as im2:
                # Convert image to GIF
                im.save(
                    output_data,
                    format="AVIF",
                    append_images=[im2],
                    save_all=True,
                    duration=500,
                    loop=0,
                )
                output_size = im.size
        else:
            # Convert to GIF with wand
            with WandImage(blob=image_data.getvalue()) as wand_image:
                # Set GIF optimization options
                wand_image.compression_quality = 80
                wand_image.quantum_operator = "dither"

                # Convert to GIF format
                wand_image.format = "gif"

                # Write to output BytesIO
                output_data.write(wand_image.make_blob("gif"))

                output_size = (wand_image.width, wand_image.height)

    output_data.seek(0)
    return output_data, output_size


# Create quote image function
async def create_quote_image(
    user: discord.User,
    content: str,
    user_mentions: Sequence[discord.User | discord.Member],
    channel_mentions: Sequence[Union[discord.abc.GuildChannel, discord.Thread]],
    role_mentions: Sequence[discord.Role],
    output_format: str,
    nickname: bool = False,
    fade: bool = True,
    light_mode: bool = False,
    bw_mode: bool = False,
    custom_quote: bool = False,
    custom_quote_user: discord.User = None,
    bot: bool = False,
) -> tuple[BytesIO, bool]:
    image_data = BytesIO()

    for user_mention in user_mentions:
        content = content.replace(user_mention.mention, f"@{user_mention.name}")

    for channel_mention in channel_mentions:
        content = content.replace(channel_mention.mention, f"#{channel_mention.name}")

    for role_mention in role_mentions:
        content = content.replace(role_mention.mention, f"@{role_mention.name}")

    content = html.escape(content)

    # Multiline code blocks
    content = re.sub(r"```(.*?)```", r"<code>\1</code>", content, flags=re.DOTALL)

    raw_lines = content.splitlines()
    processed_lines = []
    has_spoilers = False

    # Process markdown formatting
    for line in raw_lines:
        # 4chan Greentext
        if line.startswith("&gt;"):
            line = f"<span style='color: green;'>{line}</span>"

        # Remove header characters
        line = line.lstrip("### ").lstrip("## ").lstrip("# ")

        # Bold
        line = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)

        # Underline
        line = re.sub(r"__(.*?)__", r"<u>\1</u>", line)

        # Strikethrough
        line = re.sub(r"~~(.*?)~~", r"<s>\1</s>", line)

        # Italics
        line = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", line)
        line = re.sub(r"(?<!_)_([^_]+?)_(?!_)", r"<em>\1</em>", line)

        # Code
        line = re.sub(r"`([^`]+?)`", r"<code>\1</code>", line)
        line = re.sub(r"```(.*?)```", r"<code>\1</code>", line)

        # Check for spoilers
        spoilers = re.findall(r"\|\|(.*?)\|\|", line)
        if spoilers:
            line = re.sub(r"\|\|(.*?)\|\|", r"\1", line)
            has_spoilers = True

        # Discord emojis
        discord_emojis = re.findall(r"&lt;a?:\w+:\d+&gt;", line)

        processed_lines.append(line)

    content = "<br>".join(processed_lines)

    # Replace Discord emojis with image tags
    for emoji in discord_emojis:
        emoji: str
        emoji_id = emoji.split(":")[2].rstrip("&gt;")
        content = content.replace(
            emoji,
            f"<img src='https://cdn.discordapp.com/emojis/{html.escape(emoji_id)}.png' height='44' alt='{emoji}' />",
        )

    # Render Jinja2 template
    env = jinja2.Environment(
        enable_async=True,
        loader=jinja2.FileSystemLoader(os.path.join("content", "templates")),
        autoescape=True,
    )
    template = env.get_template("quote.jinja")
    quote_html = await template.render_async(
        user=user,
        content=content,
        nickname=nickname,
        fade=fade,
        light_mode=light_mode,
        bw_mode=bw_mode,
        custom_quote=custom_quote,
        custom_quote_user=custom_quote_user,
        bot=bot,
    )

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 600})

        # Set HTML content
        await page.set_content(quote_html, wait_until="networkidle")

        # Wait for images
        await page.wait_for_load_state("networkidle")

        # Take screenshot as bytes
        screenshot = await page.screenshot(
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": 1200, "height": 600},
        )

        # Write to BytesIO
        image_data.write(screenshot)
        await browser.close()

    if output_format != "PNG":
        if output_format == "GIF":
            image_data, output_size = await asyncio.to_thread(
                _to_gif,
                image_data=image_data,
                mode="compatibility",
            )
        elif output_format == "AVIF":
            image_data, output_size = await asyncio.to_thread(
                _to_gif,
                image_data=image_data,
                mode="quality",
            )

    image_data.seek(0)
    return image_data, has_spoilers


# Quotes view
class QuoteView(View):
    def __init__(
        self,
        user_id: int,
        content: str,
        user_mentions: Sequence[discord.abc.User],
        channel_mentions: Sequence[Union[discord.abc.GuildChannel, discord.Thread]],
        role_mentions: Sequence[discord.Role],
        output_format: str,
        allowed_ids: list,
        og_msg: str = None,
        nickname: bool = False,
        fade: bool = True,
        light_mode: bool = False,
        bw_mode: bool = False,
        custom_quote: bool = False,
        custom_quote_user_id: int = None,
        bot: bool = False,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.user_id = user_id
        self.content = content
        self.user_mentions = user_mentions
        self.channel_mentions = channel_mentions
        self.role_mentions = role_mentions
        self.output_format = output_format
        self.allowed_ids = allowed_ids
        self.og_msg = og_msg
        self.nickname = nickname
        self.fade = fade
        self.light_mode = light_mode
        self.bw_mode = bw_mode
        self.custom_quote = custom_quote
        self.custom_quote_user_id = custom_quote_user_id
        self.bot = bot

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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id in self.allowed_ids:
            return True
        else:
            embed = discord.Embed(
                title="Error",
                description="You can't modify this quote, as you did not run the command or get quoted.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return False

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, custom_id="theme")
    async def theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = None

        if interaction.guild is not None:
            # Try to get member if available
            user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)

        if user is None:
            try:
                user = await interaction.client.fetch_user(self.user_id)
            except discord.NotFound:
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

        if self.custom_quote:
            # Try to get member if available
            custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
            if custom_quote_user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the custom quote creator. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return
        else:
            custom_quote_user = None

        image_data, has_spoilers = await create_quote_image(
            user=user,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=not self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
            bot=self.bot,
        )

        file = discord.File(
            fp=image_data,
            filename=f"titanium_quote.{self.output_format.lower()}",
            spoiler=has_spoilers,
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            allowed_ids=self.allowed_ids,
            og_msg=self.og_msg,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=not self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
            bot=self.bot,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        if (
            interaction.guild not in interaction.client.guilds
            and interaction.guild is not None
        ):
            embed = discord.Embed(
                title="Notice",
                description="As Titanium is not in the server, I can only see the user's global nickname. To show the user's server nickname, please invite me to the server.",
                color=discord.Color.orange(),
            )
        else:
            embed = None

        await interaction.edit_original_response(
            embed=embed,
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
        user = None

        if interaction.guild is not None:
            # Try to get member if available
            user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)

        if user is None:
            try:
                user = await interaction.client.fetch_user(self.user_id)
            except discord.NotFound:
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

        if self.custom_quote:
            # Try to get member if available
            custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
            if custom_quote_user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the custom quote creator. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return
        else:
            custom_quote_user = None

        image_data, has_spoilers = await create_quote_image(
            user=user,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=self.light_mode,
            bw_mode=not self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
            bot=self.bot,
        )

        file = discord.File(
            fp=image_data,
            filename=f"titanium_quote.{self.output_format.lower()}",
            spoiler=has_spoilers,
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            allowed_ids=self.allowed_ids,
            og_msg=self.og_msg,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=self.light_mode,
            bw_mode=not self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
            bot=self.bot,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        if (
            interaction.guild not in interaction.client.guilds
            and interaction.guild is not None
        ):
            embed = discord.Embed(
                title="Notice",
                description="As Titanium is not in the server, I can only see the user's global nickname. To show the user's server nickname, please invite me to the server.",
                color=discord.Color.orange(),
            )
        else:
            embed = None

        await interaction.edit_original_response(
            embed=embed,
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
        user = None

        if interaction.guild is not None:
            # Try to get member if available
            user = interaction.guild.get_member(self.user_id)

        if user is None:
            user = interaction.client.get_user(self.user_id)

        if user is None:
            try:
                user = await interaction.client.fetch_user(self.user_id)
            except discord.NotFound:
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

        if self.custom_quote:
            # Try to get member if available
            custom_quote_user = interaction.client.get_user(self.custom_quote_user_id)
            if custom_quote_user is None:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the custom quote creator. Please try again later.",
                    color=discord.Color.red(),
                )

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True,
                )
                return
        else:
            custom_quote_user = None

        image_data, has_spoilers = await create_quote_image(
            user=user,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user=custom_quote_user,
            bot=self.bot,
        )

        file = discord.File(
            fp=image_data,
            filename=f"titanium_quote.{self.output_format.lower()}",
            spoiler=has_spoilers,
        )

        view = QuoteView(
            user_id=self.user_id,
            content=self.content,
            user_mentions=self.user_mentions,
            channel_mentions=self.channel_mentions,
            role_mentions=self.role_mentions,
            output_format=self.output_format,
            allowed_ids=self.allowed_ids,
            og_msg=self.og_msg,
            nickname=self.nickname,
            fade=self.fade,
            light_mode=self.light_mode,
            bw_mode=self.bw_mode,
            custom_quote=self.custom_quote,
            custom_quote_user_id=self.custom_quote_user_id,
            bot=self.bot,
        )

        if not self.custom_quote:
            view.add_item(
                discord.ui.Button(
                    label="Jump to Message",
                    style=discord.ButtonStyle.link,
                    url=self.og_msg,
                )
            )

        if (
            interaction.guild not in interaction.client.guilds
            and interaction.guild is not None
        ):
            embed = discord.Embed(
                title="Notice",
                description="As Titanium is not in the server, I can only see the user's global nickname. To show the user's server nickname, please invite me to the server.",
                color=discord.Color.orange(),
            )
        else:
            embed = None

        await interaction.edit_original_response(
            embed=embed,
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
        elif message.is_system():
            embed = discord.Embed(
                title="Error",
                description="You cannot quote this message, as it is a system message.",
                color=discord.Color.red(),
            )

            await interaction.followup.send(
                embed=embed,
            )

            return

        image_data, has_spoilers = await create_quote_image(
            user=message.author,
            content=message.content,
            user_mentions=message.mentions,
            channel_mentions=message.channel_mentions,
            role_mentions=message.role_mentions,
            output_format="PNG",
            nickname=True,
            bot=message.author.bot,
        )

        file = discord.File(
            fp=image_data,
            filename="titanium_quote.png",
            spoiler=has_spoilers,
        )

        view = QuoteView(
            user_id=message.author.id,
            content=message.content,
            user_mentions=message.mentions,
            channel_mentions=message.channel_mentions,
            role_mentions=message.role_mentions,
            output_format="PNG",
            allowed_ids=[interaction.user.id, message.author.id],
            og_msg=message.jump_url,
            nickname=True,
            light_mode=False,
            bw_mode=False,
            custom_quote=False,
            bot=message.author.bot,
        )
        view.add_item(
            discord.ui.Button(
                label="Jump to Message",
                style=discord.ButtonStyle.link,
                url=message.jump_url,
            )
        )

        if (
            interaction.guild not in interaction.client.guilds
            and interaction.guild is not None
        ):
            embed = discord.Embed(
                title="Notice",
                description="As Titanium is not in the server, I can only see the user's global nickname. To show the user's server nickname, please invite me to the server.",
                color=discord.Color.orange(),
            )
        else:
            embed = None

        await interaction.followup.send(embed=embed, file=file, view=view)

    @app_commands.command(
        name="quote",
        description="Create a quote image. To quote messages, right click the message, click apps, then Quote This.",
    )
    @app_commands.describe(
        user="The user to quote.",
        content="The content to quote. To quote messages, right click the message, click apps, then Quote This.",
        format="Optional: the format to use. Defaults to PNG.",
        fade="Optional: whether to apply a fade to the user's PFP. Defaults to true.",
        nickname="Optional: whether to show the user's nickname. Defaults to false.",
        light_mode="Optional: whether to start with light mode. Defaults to false.",
        bw_mode="Optional: whether to start with black and white mode. Defaults to false.",
        filename="Optional: the name of the file to save the image as. Leave blank to allow Titanium to make one for you.",
        spoiler="Optional: whether to send the image as a spoiler. Defaults to false.",
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
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.checks.cooldown(1, 5)
    async def custom_quote(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        content: str,
        format: app_commands.Choice[str] = "",
        fade: bool = True,
        nickname: bool = False,
        light_mode: bool = False,
        bw_mode: bool = False,
        filename: str = "",
        spoiler: bool = False,
    ):
        await interaction.response.defer()

        if format == "":
            format = app_commands.Choice(
                name=".png (can't be favourited, very good quality)",
                value="PNG",
            )

        # adapted from built in discord.py message.clean_content
        if interaction.guild:
            guild = interaction.guild

            def resolve_member(id: int) -> str:
                member = guild.get_member(id)
                return f"@{member.display_name if member else 'unknown-user'}"

            def resolve_channel(id: int) -> str:
                channel = guild.get_channel(id)
                return f"#{channel.name if channel else 'deleted-channel'}"

            def resolve_role(id: int) -> str:
                role = guild.get_role(id)
                return f"@{role.name if role else 'deleted-role'}"
        else:

            def resolve_member(id: int) -> str:
                user = interaction.client.get_user(id)
                if not user:
                    try:
                        self.bot.fetch_user(id)
                    except discord.NotFound:
                        user = None

                return f"@{user.name if user else 'unknown-user'}"

            def resolve_channel(id: int) -> str:
                return "#unknown-channel"

            def resolve_role(id: int) -> str:
                return "@unknown-role"

        transforms = {
            "@": resolve_member,
            "@!": resolve_member,
            "#": resolve_channel,
            "@&": resolve_role,
        }

        def repl(match: re.Match) -> str:
            type = match[1]
            id = int(match[2])
            transformed = transforms[type](id)
            return transformed

        content = re.sub(r"<(@[!&]?|#)([0-9]{15,20})>", repl, content)

        image_data, has_spoilers = await create_quote_image(
            user=user,
            content=content,
            user_mentions=[],
            channel_mentions=[],
            role_mentions=[],
            output_format=format.value,
            nickname=nickname,
            fade=fade,
            light_mode=light_mode,
            bw_mode=bw_mode,
            custom_quote=True,
            custom_quote_user=interaction.user,
        )

        file = discord.File(
            fp=image_data,
            filename=f"titanium_{filename if filename else 'quote'}.{format.value.lower()}",
            spoiler=(spoiler if spoiler else has_spoilers),
        )

        view = QuoteView(
            user_id=user.id,
            content=content,
            user_mentions=[],
            channel_mentions=[],
            role_mentions=[],
            output_format=format.value,
            allowed_ids=[interaction.user.id, user.id],
            nickname=nickname,
            fade=fade,
            light_mode=light_mode,
            bw_mode=bw_mode,
            custom_quote=True,
            custom_quote_user_id=interaction.user.id,
        )

        if (
            interaction.guild not in interaction.client.guilds
            and interaction.guild is not None
        ):
            embed = discord.Embed(
                title="Notice",
                description="As Titanium is not in the server, I can only see the user's global nickname. To show the user's server nickname, please invite me to the server.",
                color=discord.Color.orange(),
            )
        else:
            embed = None

        await interaction.followup.send(embed=embed, file=file, view=view)


async def setup(bot):
    await bot.add_cog(Quotes(bot))
