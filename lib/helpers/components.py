import discord
from discord.utils import escape_markdown, escape_mentions


def escape_all(text: str) -> str:
    return escape_markdown(escape_mentions(text))


def embed_to_v2(embed: discord.Embed) -> discord.ui.LayoutView:
    container = discord.ui.Container()
    container.accent_colour = embed.colour

    text_parts = []
    thumbnail = None
    image = None

    if embed.author.name:
        text_parts.append(f"-# {escape_all(embed.author.name)}")

    if embed.title:
        text_parts.append(f"## {escape_mentions(embed.title.replace('#', '\\#'))}")

    if embed.description:
        text_parts.append(escape_mentions(embed.description))

    if embed.footer.text:
        text_parts.append(f"-# {escape_all(embed.footer.text)}")

    if embed.thumbnail.url:
        thumbnail = discord.ui.Thumbnail(media=embed.thumbnail.url)

    if embed.image.url:
        image = discord.ui.MediaGallery(discord.MediaGalleryItem(media=embed.image.url))

    if thumbnail:
        container.add_item(discord.ui.Section("\n".join(text_parts), accessory=thumbnail))
    else:
        container.add_item(discord.ui.TextDisplay("\n".join(text_parts)))

    if image:
        container.add_item(image)

    return discord.ui.LayoutView().add_item(container)
