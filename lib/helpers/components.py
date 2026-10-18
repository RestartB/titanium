import discord
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    MediaGallery,
    Section,
    Separator,
    TextDisplay,
    Thumbnail,
)
from discord.utils import escape_markdown, escape_mentions

from lib.api.validators import Cv2Component
from lib.enums.cv2 import ComponentType


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


def tiToCv2(data: list) -> LayoutView:
    cps: list[Cv2Component] = []
    for item in data:
        cps.append(Cv2Component(**item))

    view = LayoutView()
    container = Container(accent_colour=discord.Colour.light_grey())

    for cp in cps:
        if cp.cId == ComponentType.TEXT_DISPLAY and cp.content:
            container.add_item(TextDisplay(cp.content))
        elif cp.cId == ComponentType.TEXT_THUMBNAIL and cp.content and cp.url:
            container.add_item(Section(TextDisplay(cp.content), accessory=Thumbnail(str(cp.url))))
        elif cp.cId == ComponentType.BUTTON_ROW and cp.buttons:
            row = ActionRow()
            for button in cp.buttons:
                row.add_item(
                    Button(label=button.label, url=str(button.url), style=discord.ButtonStyle.url)
                )

            container.add_item(row)
        elif cp.cId == ComponentType.MEDIA_GALLERY and cp.urls:
            gallery = MediaGallery()
            for url in cp.urls:
                gallery.add_item(media=str(url))

            container.add_item(gallery)
        elif cp.cId == ComponentType.SEPARATOR:
            container.add_item(
                Separator(
                    spacing=(
                        discord.SeparatorSpacing.small
                        if cp.spacing == 1
                        else discord.SeparatorSpacing.large
                    )
                )
            )

    view.add_item(container)
    return view
