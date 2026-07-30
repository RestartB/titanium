import asyncio
import base64
import html
import os
import re
import uuid
from io import BytesIO
from pathlib import Path

import discord
import jinja2
from PIL import Image

from lib.classes.browser import BrowserRenderer
from lib.classes.img_tools import ImageTools
from lib.classes.quote_config import QuoteData
from lib.helpers.shorten import shorten_preserve


# Create quote image function
async def create_quote_image(data: QuoteData, renderer: BrowserRenderer) -> discord.File:
    image_data = BytesIO()
    content = data.content

    def protect_escaped_markdown(match: re.Match[str]) -> str:
        identifier = f"ESCAPEDMD{uuid.uuid4().hex}"
        escaped_markdown[identifier] = match.group(1)
        return identifier

    # protect escaped markdown
    escaped_markdown: dict[str, str] = {}
    content = re.sub(
        r"\\([\\`*_~|>#])",
        protect_escaped_markdown,
        content,
    )

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
        line = line.removeprefix("### ").removeprefix("## ").removeprefix("# ")

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

    # restore escaped markdown
    for identifier, markdown in escaped_markdown.items():
        content = content.replace(identifier, markdown)

    # Render Jinja2 template
    env = jinja2.Environment(
        enable_async=True,
        loader=jinja2.FileSystemLoader(os.path.join("lib", "templates")),
        autoescape=True,
    )
    template = env.get_template("quote.jinja")

    pfp_base64 = base64.b64encode(data.pfp_data.getvalue()).decode("ascii")
    pfp_src = f"data:image/png;base64,{pfp_base64}"

    font_path = Path("lib/fonts/figtree.ttf")
    font_base64 = base64.b64encode(font_path.read_bytes()).decode("ascii")

    quote_html = await template.render_async(
        font_base64=font_base64,
        content=content,
        user=data.user,
        user_pfp=pfp_src,
        nickname=data.nickname,
        fade=data.fade,
        light_mode=data.light_mode,
        bw_mode=data.bw_mode,
        custom_quote=data.custom_quote,
        custom_quote_user=data.runner_user,
        is_bot=data.user.bot,
    )

    screenshot = await renderer.screenshot_html(
        quote_html,
        selector="body",
        viewport_width=1200,
        viewport_height=600,
    )
    image_data.write(screenshot)

    if data.output_format != "PNG":
        tools = ImageTools()
        image_data = await asyncio.to_thread(
            tools._save_sync,
            img=Image.open(image_data),
            output_format=data.output_format,
            quality=95,
        )

    image_data.seek(0)

    return discord.File(
        image_data,
        filename=f"titanium_quote.{data.output_format.value.lower()}",
        spoiler=has_spoilers,
        description=shorten_preserve(data.content, width=1024),
    )
