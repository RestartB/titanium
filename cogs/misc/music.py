import os
from io import BytesIO
from textwrap import shorten
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
import spotipy
from colorthief import ColorThief
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import Select, View
from discord.utils import escape_markdown
from spotipy.oauth2 import SpotifyClientCredentials

import lib.embeds.spotify as elements
from lib.helpers.hybrid_adapters import defer, stop_loading
from lib.helpers.log_error import log_error

if TYPE_CHECKING:
    from main import TitaniumBot


class MusicCommandsCog(
    commands.Cog, name="Music", description="Search Spotify and get song lyrics."
):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot
        self.auth_manager = SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_API_ID"),
            client_secret=os.getenv("SPOTIFY_API_SECRET"),
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    @commands.hybrid_group(name="spotify")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def spotify_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    async def song_search_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Strip whitespace, cap at 100 characters
        current = current.strip()[:100]

        if current and current != "":
            # Check if search is Spotify ID
            if len(current) == 22 and " " not in current:
                try:
                    item: Any = self.sp.track(current)

                    options = [
                        app_commands.Choice(
                            name="Spotify ID detected, send command now to get info",
                            value=current,
                        )
                    ]

                    title = shorten(
                        text=f"{'(E) ' if item['explicit'] else ''}{item['name']}",
                        width=50,
                        placeholder="...",
                    )

                    artists = shorten(
                        ", ".join(
                            [artist["name"] for artist in item["artists"]],
                        ),
                        width=22,
                        placeholder="...",
                    )

                    album = shorten(text=item["album"]["name"], width=22, placeholder="...")

                    options.append(
                        app_commands.Choice(
                            name=(f"{title} - {artists} ({album})"),
                            value=item["id"],
                        )
                    )

                    return options
                except spotipy.exceptions.SpotifyException:
                    pass

            options = [
                app_commands.Choice(
                    name=current,
                    value=current,
                )
            ]

            try:
                result = self.sp.search(current, type="track", limit=5)
            except spotipy.exceptions.SpotifyException:
                return [
                    app_commands.Choice(
                        name="Spotify error, send command now to search again",
                        value=current,
                    )
                ]

            if result is None:
                return [
                    app_commands.Choice(
                        name="No results found, send command now to search again",
                        value=current,
                    )
                ]

            if len(result["tracks"]["items"]) == 0:
                return [
                    app_commands.Choice(
                        name="No results found, send command now to search again",
                        value=current,
                    )
                ]
            else:
                for item in result["tracks"]["items"]:
                    title = shorten(
                        text=f"{'(E) ' if item['explicit'] else ''}{item['name']}",
                        width=50,
                        placeholder="...",
                    )

                    artists = shorten(
                        ", ".join(
                            [artist["name"] for artist in item["artists"]],
                        ),
                        width=22,
                        placeholder="...",
                    )

                    album = shorten(text=item["album"]["name"], width=22, placeholder="...")

                    options.append(
                        app_commands.Choice(
                            name=(f"{title} - {artists} ({album})"),
                            value=item["id"],
                        )
                    )

            return options
        else:
            return [
                app_commands.Choice(
                    name="Enter a song name / lyrics, or enter a song ID and send command",
                    value=current,
                )
            ]

    # Spotify Song Search command
    @spotify_group.command(name="song", description="Search for a song on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=song_search_autocomplete)
    async def spotify_song(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        search: commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ) -> None:
        await defer(self.bot, ctx, ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No search term provided.",
                color=Color.red(),
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.track(search)

                await elements.song(
                    bot=self.bot,
                    sp=self.sp,
                    item=item,
                    ctx=ctx,
                    ephemeral=ephemeral,
                )

                return
            except spotipy.exceptions.SpotifyException:
                pass

        # Search Spotify
        result = self.sp.search(search, type="track", limit=10)

        if result is None:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if result is blank
        if len(result["tracks"]["items"]) == 0:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
        else:
            # Sort through request data
            i = 0
            for item in result["tracks"]["items"]:
                if item["explicit"]:
                    if len(item["name"]) > 86:
                        label = item["name"][:86] + "... (Explicit)"
                    else:
                        label = item["name"] + " (Explicit)"
                else:
                    if len(item["name"]) > 100:
                        label = item["name"][:97] + "..."
                    else:
                        label = item["name"]

                artist_string = ""

                for artist in item["artists"]:
                    if artist_string == "":
                        artist_string = artist["name"]
                    else:
                        artist_string += f", {artist['name']}"

                if len(f"{artist_string} - {item['album']['name']}") > 100:
                    description = f"{artist_string} - {item['album']['name']}"[:97] + "..."
                else:
                    description = f"{artist_string} - {item['album']['name']}"

                options_list.append(
                    discord.SelectOption(label=label, description=description, value=str(i))
                )
                i += 1

            # Define options
            select = Select(options=options_list)

            embed = discord.Embed(
                title="Select Song",
                description=f'Showing {len(result["tracks"]["items"])} results for "{search}"',
                color=Color.random(),
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                # Find unique ID of selection in the list
                item = result["tracks"]["items"][int(select.values[0])]

                await elements.song(
                    bot=self.bot,
                    sp=self.sp,
                    item=item,
                    ctx=ctx,
                    ephemeral=ephemeral,
                    responded=True,
                    respond_msg=msg,
                )

        # Set up list with provided values
        select.callback = response
        view = View()
        view.add_item(select)

        # Edit initial message to show dropdown
        msg = await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)

    async def artist_search_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Strip whitespace, cap at 100 characters
        current = current.strip()[:100]

        if current and current != "":
            # Check if search is Spotify ID
            if len(current) == 22 and " " not in current:
                try:
                    item = self.sp.artist(current)

                    if item is None:
                        return [
                            app_commands.Choice(
                                name="Spotify error, send command now to search again",
                                value=current,
                            )
                        ]

                    options = [
                        app_commands.Choice(
                            name="Spotify ID detected, send command now to get info",
                            value=current,
                        )
                    ]

                    options.append(
                        app_commands.Choice(
                            name=shorten(text=item["name"], width=100, placeholder="..."),
                            value=item["id"],
                        )
                    )

                    return options
                except spotipy.exceptions.SpotifyException:
                    pass

            options = [
                app_commands.Choice(
                    name=current,
                    value=current,
                )
            ]

            try:
                result = self.sp.search(current, type="artist", limit=5)

                if result is None:
                    raise ValueError
            except (spotipy.exceptions.SpotifyException, ValueError):
                return [
                    app_commands.Choice(
                        name="Spotify error, send command now to search again",
                        value=current,
                    )
                ]

            if len(result["artists"]["items"]) == 0:
                options = [
                    app_commands.Choice(
                        name="No results found, send command now to search again",
                        value=current,
                    )
                ]
            else:
                for item in result["artists"]["items"]:
                    options.append(
                        app_commands.Choice(
                            name=shorten(text=item["name"], width=100, placeholder="..."),
                            value=item["id"],
                        )
                    )

            return options
        else:
            return [
                app_commands.Choice(
                    name="Enter a song name, or enter a song ID and send command",
                    value=current,
                )
            ]

    # Spotify Artist Search command
    @spotify_group.command(name="artist", description="Search for an artist on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=artist_search_autocomplete)
    async def spotify_artist(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        search: commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ) -> None:
        await defer(self.bot, ctx, ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No search term provided.",
                color=Color.red(),
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.artist(search)

                if item is None:
                    raise ValueError

                top_tracks = self.sp.artist_top_tracks(item["id"])

                await elements.artist(
                    sp=self.sp,
                    item=item,
                    top_tracks=top_tracks,
                    ctx=ctx,
                    ephemeral=ephemeral,
                )

                return
            except (spotipy.exceptions.SpotifyException, ValueError):
                pass

        # Search Spotify
        result = self.sp.search(search, type="artist", limit=10)

        if result is None:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if result is blank
        if len(result["artists"]["items"]) == 0:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
        else:
            # Sort through request data
            i = 0
            for item in result["artists"]["items"]:
                if len(item["name"]) > 100:
                    title = item["name"][:97] + "..."
                else:
                    title = item["name"]

                options_list.append(discord.SelectOption(label=title, value=str(i)))
                i += 1

            # Define options
            select = Select(options=options_list)

            embed = discord.Embed(
                title="Select Artist",
                description=f'Showing {len(result["artists"]["items"])} results for "{search}"',
                color=Color.random(),
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                item = result["artists"]["items"][int(select.values[0])]

                result_info = self.sp.artist(item["id"])

                result_top_tracks = self.sp.artist_top_tracks(item["id"])

                await elements.artist(
                    sp=self.sp,
                    item=result_info,
                    top_tracks=result_top_tracks,
                    ctx=ctx,
                    ephemeral=ephemeral,
                    responded=True,
                    respond_msg=msg,
                )

            # Set up list with provided values
            select.callback = response
            view = View()
            view.add_item(select)

            # Edit initial message to show dropdown
            msg = await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)

    async def album_search_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Strip whitespace, cap at 100 characters
        current = current.strip()[:100]

        if current and current != "":
            # Check if search is Spotify ID
            if len(current) == 22 and " " not in current:
                try:
                    item = self.sp.album(current)

                    if item is None:
                        return [
                            app_commands.Choice(
                                name="Spotify error, send command now to search again",
                                value=current,
                            )
                        ]

                    options = [
                        app_commands.Choice(
                            name="Spotify ID detected, send command now to get info",
                            value=current,
                        )
                    ]

                    # Generate artist list
                    artists_list = []
                    for artist in item["artists"]:
                        artists_list.append(artist["name"])

                    artists = shorten(text=", ".join(artists_list), width=32, placeholder="...")

                    options.append(
                        app_commands.Choice(
                            name=f"{shorten(text=item['name'], width=65, placeholder='...')} - {artists}",
                            value=item["id"],
                        )
                    )

                    return options
                except spotipy.exceptions.SpotifyException:
                    pass

            options = [
                app_commands.Choice(
                    name=current,
                    value=current,
                )
            ]

            try:
                result = self.sp.search(current, type="album", limit=5)

                if result is None:
                    raise ValueError
            except (spotipy.exceptions.SpotifyException, ValueError):
                return [
                    app_commands.Choice(
                        name="Spotify error, send command now to search again",
                        value=current,
                    )
                ]

            if len(result["albums"]["items"]) == 0:
                options = [
                    app_commands.Choice(
                        name="No results found, send command now to search again",
                        value=current,
                    )
                ]
            else:
                for item in result["albums"]["items"]:
                    # Generate artist list
                    artists_list = []
                    for artist in item["artists"]:
                        artists_list.append(artist["name"])

                    artists = shorten(text=", ".join(artists_list), width=32, placeholder="...")

                    options.append(
                        app_commands.Choice(
                            name=f"{shorten(text=item['name'], width=65, placeholder='...')} - {artists}",
                            value=item["id"],
                        )
                    )

            return options
        else:
            return [
                app_commands.Choice(
                    name="Enter a song name, or enter a song ID and send command",
                    value=current,
                )
            ]

    # Spotify Album Search command
    @spotify_group.command(name="album", description="Search for an album on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=album_search_autocomplete)
    async def spotify_album(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        search: commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ) -> None:
        await defer(self.bot, ctx, ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No search term provided.",
                color=Color.red(),
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.album(search)

                await elements.album(
                    sp=self.sp,
                    item=item,
                    ctx=ctx,
                    ephemeral=ephemeral,
                )

                return
            except spotipy.exceptions.SpotifyException:
                pass

        # Search Spotify
        result = self.sp.search(search, type="album", limit=10)

        if result is None:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        # Check if result is blank
        if len(result["albums"]["items"]) == 0:
            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} No results found.",
                color=Color.red(),
            )
            await ctx.reply(embed=embed)
        else:
            # Sort through request data
            i = 0
            for item in result["albums"]["items"]:
                artist_string = ""
                for artist in item["artists"]:
                    if artist_string == "":
                        artist_string = escape_markdown(artist["name"])
                    else:
                        artist_string += f", {escape_markdown(artist['name'])}"

                if len(item["name"]) > 100:
                    title = item["name"][:97] + "..."
                else:
                    title = item["name"]

                if len(artist_string) > 100:
                    description = artist_string[:97] + "..."
                else:
                    description = artist_string

                options_list.append(
                    discord.SelectOption(label=title, description=description, value=str(i))
                )
                i += 1

            # Define options
            select = Select(options=options_list)

            embed = discord.Embed(
                title="Select Album",
                description=f'Showing {len(result["albums"]["items"])} results for "{search}"',
                color=Color.random(),
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                item = result["albums"]["items"][int(select.values[0])]

                result_info = self.sp.album(item["id"])

                await elements.album(
                    sp=self.sp,
                    item=result_info,
                    ctx=ctx,
                    ephemeral=ephemeral,
                    responded=True,
                    respond_msg=msg,
                )

            # Set up list with provided values
            select.callback = response
            view = View()
            view.add_item(select)

            # Edit initial message to show dropdown
            msg = await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)

    # Spotify Image command
    @spotify_group.command(
        name="image", description="Get high quality album art from a Spotify URL."
    )
    @app_commands.describe(
        url="The target Spotify URL. Song, album, playlist and spotify.link URLs are supported.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def spotify_image(
        self, ctx: commands.Context["TitaniumBot"], url: str, ephemeral: bool = False
    ) -> None:
        await defer(bot=self.bot, ctx=ctx, ephemeral=ephemeral)

        if "spotify.link" in url:
            try:
                # noinspection HttpUrlsUsage
                url = (
                    url.replace("www.", "")
                    .replace("http://", "")
                    .replace("https://", "")
                    .rstrip("/")
                )
                url = f"https://{url}"

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as request:
                        url = str(request.url)

            except Exception as error:
                error_id = await log_error(
                    module="Spotify",
                    guild_id=ctx.guild.id if ctx.guild else None,
                    error="Failed to expand Spotify URL",
                    exc=error,
                )

                embed = discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Couldn't expand URL",
                    description="A **spotify.link** URL was detected, but we could not expand it. Is it valid?\n\nIf you are sure the URL is valid and supported, please try again later.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{ctx.author.name} - {error_id}",
                    icon_url=ctx.author.display_avatar.url,
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
                await stop_loading(self.bot, ctx)

                return

        artist_string = ""

        try:
            if "track" in url:
                result = self.sp.track(url)

                if result is None:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No results found.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
                    return

                for artist in result["artists"]:
                    if artist_string == "":
                        artist_string = artist["name"]
                    else:
                        artist_string += f", {artist['name']}"

                if result["album"]["images"] is not None:
                    image_url = result["album"]["images"][0]["url"]

                    # Get image, store in memory
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as request:
                            image_data = BytesIO()

                            async for chunk in request.content.iter_chunked(10):
                                image_data.write(chunk)

                            image_data.seek(0)

                    # Get dominant colour for embed
                    color_thief = ColorThief(image_data)
                    dominant_color = color_thief.get_color()

                    if (
                        result["album"]["images"][0]["height"] is None
                        or result["album"]["images"][0]["width"] is None
                    ):
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string})",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string})",
                            description=f"Viewing highest quality ({result['album']['images'][0]['width']}x{result['album']['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                    embed.set_image(url=result["album"]["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Open in Browser",
                            style=discord.ButtonStyle.url,
                            url=result["album"]["images"][0]["url"],
                        )
                    )

                    await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No album art available.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
            elif "album" in url:
                result = self.sp.album(url)

                if result is None:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No results found.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
                    return

                image_url = result["images"][0]["url"]

                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(10):
                            image_data.write(chunk)

                        image_data.seek(0)

                # Get dominant colour for embed
                color_thief = ColorThief(image_data)
                dominant_color = color_thief.get_color()

                for artist in result["artists"]:
                    if artist_string == "":
                        artist_string = artist["name"]
                    else:
                        artist_string += f", {artist['name']}"

                if result["images"] is not None:
                    if (
                        result["images"][0]["height"] is None
                        or result["images"][0]["width"] is None
                    ):
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string})",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string})",
                            description=f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    embed.set_image(url=result["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Download",
                            style=discord.ButtonStyle.url,
                            url=result["images"][0]["url"],
                        )
                    )

                    await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No album art available.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
            # Playlist URL
            elif "playlist" in url:
                # Search playlist on Spotify
                result = self.sp.playlist(url, market="GB")

                if result is None:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No results found.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
                    return

                image_url = result["images"][0]["url"]

                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(10):
                            image_data.write(chunk)

                        image_data.seek(0)

                # Get dominant colour for embed
                color_thief = ColorThief(image_data)
                dominant_color = color_thief.get_color()

                if result["images"] is not None:
                    if (
                        result["images"][0]["height"] is None
                        or result["images"][0]["width"] is None
                    ):
                        embed = discord.Embed(
                            title=f"{result['name']} - {result['owner']['display_name']} (Playlist)",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} - {result['owner']['display_name']} (Playlist)",
                            description=f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    embed.set_image(url=result["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Download",
                            style=discord.ButtonStyle.url,
                            url=result["images"][0]["url"],
                        )
                    )

                    await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)
                else:
                    embed = discord.Embed(
                        title=f"{str(self.bot.error_emoji)} No cover art available.",
                        color=Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )
                    await ctx.reply(embed=embed, ephemeral=ephemeral)
            else:
                embed = discord.Embed(
                    title=f"{str(self.bot.error_emoji)} Invalid URL",
                    description="Only `track`, `album` and `playlist` URLs are supported by this command.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{ctx.author.name}",
                    icon_url=ctx.author.display_avatar.url,
                )
                await ctx.reply(embed=embed, ephemeral=ephemeral)
        except spotipy.exceptions.SpotifyException as error:
            error_id = await log_error(
                module="Spotify",
                guild_id=ctx.guild.id if ctx.guild else None,
                error="Spotify error occurred while searching URL",
                exc=error,
            )

            embed = discord.Embed(
                title=f"{str(self.bot.error_emoji)} Spotify Error",
                description="An unknown Spotify error occurred while processing the URL. Please try again later.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{ctx.author.name} - {error_id}",
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.reply(embed=embed, ephemeral=ephemeral)
        finally:
            await stop_loading(self.bot, ctx)


async def setup(bot: TitaniumBot) -> None:
    # Only load if Spotify API keys are present
    if os.getenv("SPOTIFY_API_ID") is not None and os.getenv("SPOTIFY_API_SECRET") is not None:
        if os.getenv("SPOTIFY_API_ID") != "" and os.getenv("SPOTIFY_API_SECRET") != "":
            await bot.add_cog(MusicCommandsCog(bot))
