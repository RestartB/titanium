from io import BytesIO
from textwrap import shorten
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
import discord
from colorthief import ColorThief
from discord import Color
from discord.ext import commands
from discord.utils import escape_markdown

from lib.views.pagination import PaginationView
from lib.views.spotify import AlbumMenuButton, ArtistView, SongView

if TYPE_CHECKING:
    import spotipy

    from main import TitaniumBot


# Song element function
async def song(
    bot: TitaniumBot,
    sp: spotipy.Spotify,
    item: dict | Any,
    ctx: commands.Context["TitaniumBot"],
    add_button_url: Optional[str] = None,
    add_button_text: Optional[str] = None,
    cached: bool = False,
    ephemeral: bool = False,
    responded: bool = False,
    respond_msg: Optional[discord.Message] = None,
):
    """
    Handle Spotify song embeds.
    """

    artist_data = sp.artist(item["artists"][0]["external_urls"]["spotify"])
    artist_img = ""

    if artist_data is not None:
        artist_img = artist_data["images"][0]["url"]

    artist_string = ""
    for artist in item["artists"]:
        if artist_string == "":
            artist_string = artist["name"]
        else:
            artist_string += f", {artist['name']}"

    explicit = item["explicit"]

    # Set up new embed
    embed = discord.Embed(
        title=f"{item['name']}{f' {bot.explicit_emoji}' if explicit else ''}",
        description=f"on **[{escape_markdown(item['album']['name'])}](<{item['album']['external_urls']['spotify']}>) • {item['album']['release_date'].split('-', 1)[0]}**",
    )

    embed.set_thumbnail(url=item["album"]["images"][0]["url"])
    embed.set_author(
        name=artist_string,
        url=item["artists"][0]["external_urls"]["spotify"],
        icon_url=artist_img,
    )
    embed.set_footer(
        text=f"@{ctx.author.name}{' • Cached Result' if cached else ''}",
        icon_url=ctx.author.display_avatar.url,
    )

    # Get image, store in memory
    async with aiohttp.ClientSession() as session:
        async with session.get(item["album"]["images"][0]["url"]) as request:
            image_data = BytesIO()

            async for chunk in request.content.iter_chunked(10):
                image_data.write(chunk)

            image_data.seek(0)  # Reset buffer position to start

    # Get dominant colour for embed
    color_thief = ColorThief(image_data)
    colours = color_thief.get_color()

    embed.color = Color.from_rgb(r=colours[0], g=colours[1], b=colours[2])

    view = SongView(
        item=item,
        colours=colours,
        add_button_url=add_button_url,
        add_button_text=add_button_text,
    )

    if responded and respond_msg:
        await respond_msg.edit(embed=embed, view=view)
    else:
        await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)


# Artist element function
async def artist(
    sp: spotipy.Spotify,
    item: dict | Any,
    top_tracks: dict | Any,
    ctx: commands.Context["TitaniumBot"],
    ephemeral: bool = False,
    responded: bool = False,
    respond_msg: Optional[discord.Message] = None,
):
    """
    Handle Spotify artist embeds.
    """

    embed = discord.Embed(title=f"{item['name']}")

    embed.add_field(name="Followers", value=f"{item['followers']['total']:,}")
    embed.set_thumbnail(url=item["images"][0]["url"])

    embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

    try:
        topsong_string = ""
        for i in range(0, 5):
            artist_string = ""
            for artist in top_tracks["tracks"][i]["artists"]:
                if artist_string == "":
                    artist_string = escape_markdown(artist["name"])
                else:
                    artist_string += f", {escape_markdown(artist['name'])}"

            # Hide artist string from song listing if there is only one artist
            if len(top_tracks["tracks"][i]["artists"]) == 1:
                if topsong_string == "":
                    topsong_string = (
                        f"{i + 1}. **{escape_markdown(top_tracks['tracks'][i]['name'])}**"
                    )
                else:
                    topsong_string += (
                        f"\n{i + 1}. **{escape_markdown(top_tracks['tracks'][i]['name'])}**"
                    )
            else:
                if topsong_string == "":
                    topsong_string = f"{i + 1}. **{escape_markdown(top_tracks['tracks'][i]['name'])}** - {artist_string}"
                else:
                    topsong_string += f"\n{i + 1}. **{escape_markdown(top_tracks['tracks'][i]['name'])}** - {artist_string}"

        embed.add_field(name="Top Songs", value=topsong_string, inline=False)
    except IndexError:
        pass

    # Get image, store in memory
    async with aiohttp.ClientSession() as session:
        async with session.get(item["images"][0]["url"]) as request:
            image_data = BytesIO()

            async for chunk in request.content.iter_chunked(10):
                image_data.write(chunk)

            image_data.seek(0)  # Reset buffer position to start

    # Get dominant colour for embed
    color_thief = ColorThief(image_data)
    colours = color_thief.get_color()

    embed.color = Color.from_rgb(r=colours[0], g=colours[1], b=colours[2])

    view = ArtistView(
        item=item,
        colours=colours,
        op_id=ctx.author.id,
    )

    if responded and respond_msg:
        await respond_msg.edit(embed=embed, view=view)
    else:
        await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)


# Album element function
async def album(
    sp: spotipy.Spotify,
    item: dict | Any,
    ctx: commands.Context["TitaniumBot"],
    add_button_url: Optional[str] = None,
    add_button_text: Optional[str] = None,
    ephemeral: bool = False,
    responded: bool = False,
    respond_msg: Optional[discord.Message] = None,
):
    """
    Handle Spotify album embeds.
    """

    artist_data = sp.artist(item["artists"][0]["external_urls"]["spotify"])
    artist_img = ""

    if artist_data is not None:
        artist_img = artist_data["images"][0]["url"]

    pages = []
    page = [f"*Released **{item['release_date']}***\n"]

    # Generate artist list
    artists_list = []
    for artist in item["artists"]:
        artists_list.append(escape_markdown(artist["name"]))

    artists = shorten(", ".join(artists_list), width=256, placeholder="...")

    # Generate pages with 15 items
    for i, track in enumerate(item["tracks"]["items"]):
        # Generate track artist list
        track_artists_list = []
        for artist in track["artists"]:
            track_artists_list.append(escape_markdown(artist["name"]))

        # Only show artists if they are not the same as the album artist
        if track_artists_list == artists_list:
            page.append(f"{i + 1}. **{shorten(track['name'], width=200, placeholder='...')}**")
        else:
            track_artists = shorten(", ".join(track_artists_list), width=100, placeholder="...")

            page.append(
                f"{i + 1}. **{shorten(escape_markdown(item['tracks']['items'][i]['name']), width=100, placeholder='...')}** - {track_artists}"
            )

        # Make new page if current page is full
        if len(page) == 16:
            pages.append("\n".join(page))
            page = [f"*Released **{item['release_date']}***\n"]

    # Catch if page is not empty
    if page != []:
        pages.append("\n".join(page))

    # Get image, store in memory
    async with aiohttp.ClientSession() as session:
        async with session.get(item["images"][0]["url"]) as request:
            image_data = BytesIO()

            async for chunk in request.content.iter_chunked(10):
                image_data.write(chunk)

            image_data.seek(0)  # Reset buffer position to start

    # Get dominant colour for embed
    color_thief = ColorThief(image_data)
    colours = color_thief.get_color()

    page_embeds = []
    for page in pages:
        embed = discord.Embed(
            title=item["name"],
            description=page,
            color=Color.from_rgb(r=colours[0], g=colours[1], b=colours[2]),
        )
        embed.set_author(
            name=artists,
            url=item["artists"][0]["external_urls"]["spotify"],
            icon_url=artist_img,
        )
        embed.set_thumbnail(url=item["images"][0]["url"])

        page_embeds.append(embed)

    if len(page_embeds) > 1:
        view = PaginationView(
            embeds=page_embeds,
            timeout=300,
            custom_buttons=[
                AlbumMenuButton(
                    item=item,
                    artists=artists,
                    artist_img=artist_img,
                    colours=colours,
                    add_button_url=add_button_url,
                    add_button_text=add_button_text,
                )
            ],
        )

    if responded and respond_msg:
        await respond_msg.edit(embed=page_embeds[0], view=view if view else None)
    else:
        if view:
            await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)
        else:
            await ctx.reply(embed=page_embeds[0], ephemeral=ephemeral)
