import asyncio
import datetime
import logging
from io import BytesIO
from urllib.parse import quote

import aiohttp
import asqlite
import discord
import spotipy
from colorthief import ColorThief
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View
from discord.utils import escape_markdown
from spotipy.oauth2 import SpotifyClientCredentials
from url_cleaner import UrlCleaner

import utils.songlink_exceptions as songlink_exceptions
import utils.spotify_elements as elements


def _fetch_playlist_items(self, result_info, url) -> list:
    total_items = result_info["tracks"]["total"]

    amount_spotify_pages = total_items // 100
    if total_items % 100 != 0:
        amount_spotify_pages += 1

    # Variables
    i = 0
    pages = []
    page_str = ""

    for current in range(amount_spotify_pages):
        result_current = self.sp.playlist_items(
            url, market="GB", offset=(current * 100)
        )
        # Work through all tracks in playlist, adding them to a page
        for playlist_item in result_current["items"]:
            try:
                i += 1
                artist_string = ""

                # Check if item is a track, podcast, unavailable in current reigon or unknown
                if playlist_item["track"] is None:
                    # Item type is unavailable in the GB reigon
                    # If there's nothing in the current page, make a new one
                    if page_str == "":
                        page_str = f"{i}. *(Media Unavailable)*"
                    # Else, add string to existing page
                    else:
                        page_str += f"\n{i}. *(Media Unavailable)*"
                elif playlist_item["track"]["type"] == "track":
                    # Item is a track
                    # Work through all artists of item
                    for artist in playlist_item["track"]["artists"]:
                        # If there is no artists already in the artist string
                        if artist_string == "":
                            # We set the artist string to the artist we're currently on
                            artist_string = artist["name"].replace("*", "-")
                        else:
                            # Else, we add the current artist to the existing artist string
                            artist_string += f", {artist['name']}".replace("*", "-")

                    # If there's nothing in the current page, make a new one
                    if page_str == "":
                        page_str = f"{i}. **{escape_markdown(playlist_item['track']['name'])}** - {artist_string}"
                    # Else, add string to existing page
                    else:
                        page_str += f"\n{i}. **{escape_markdown(playlist_item['track']['name'])}** - {artist_string}"
                elif playlist_item["track"]["type"] == "episode":
                    # Item is a podcast
                    if page_str == "":
                        page_str = f"{i}. **{escape_markdown(playlist_item['track']['album']['name'])}** - {escape_markdown(playlist_item['track']['name'])} (Podcast)"
                    else:
                        page_str += f"\n{i}. **{escape_markdown(playlist_item['track']['album']['name'])}** - {escape_markdown(playlist_item['track']['name'])} (Podcast)"
                else:
                    # Item type is unknown / unsupported
                    # If there's nothing in the current page, make a new one
                    if page_str == "":
                        page_str = f"{i}. *(Unknown Media Type)*"
                    # Else, add string to existing page
                    else:
                        page_str += f"\n{i}. *(Unknown Media Type)*"
            except KeyError:
                # Create new page if current page is empty
                if page_str == "":
                    page_str = f"{i}. *(Media Unavailable)*"
                # Else, add string to existing page
                else:
                    page_str += f"\n{i}. *(Media Unavailable)*"

            # If there's 15 items in the current page, we split it into a new page
            if i % 15 == 0:
                pages.append(page_str)
                page_str = ""

    # If there is still data in page_str, add it to a new page
    if page_str != "":
        pages.append(page_str)
        page_str = ""

    return pages


class SongURL(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(
            client_id=self.bot.tokens["spotify-api-id"],
            client_secret=self.bot.tokens["spotify-api-secret"],
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

        self.cache_pool: asqlite.Pool = bot.cache_pool

        self.cleaner = UrlCleaner()
        self.cleaner.ruler.update_rules()

        # Setup
        self.bot.loop.create_task(self.setup())

    # List refresh function
    async def setup(self):
        async with self.cache_pool.acquire() as sql:
            # song.link Cache - store previous results
            await sql.execute(
                "CREATE TABLE IF NOT EXISTS songlinkCache (userURL text, spotifyURL text, platformRich text, platformRaw text, ttl int)"
            )
            await sql.commit()

            self.cache = await sql.fetchall("SELECT * FROM songlinkCache")

    # List refresh function
    async def refresh_cache(self):
        async with self.cache_pool.acquire() as sql:
            self.cache = await sql.fetchall("SELECT * FROM songlinkCache")

    # Song URL command
    @app_commands.command(name="song-url", description="Get info about a song link.")
    @app_commands.describe(
        url="The target URL. Run /song-link-help for supported link types."
    )
    @app_commands.describe(
        bypass_cache="Bypass the cache to get a new result for non-Spotify links. Can help if provided match is wrong."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 10)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def song_url(
        self,
        interaction: discord.Interaction,
        url: str,
        bypass_cache: bool = False,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        og_url = url
        url = self.cleaner.clean(url)

        async def songlink_request(user_url):
            try:
                processed_source = quote(user_url, safe="()*!'")
                request_url = f"https://api.song.link/v1-alpha.1/links?url={processed_source}&userCountry=GB"

                # Send request to song.link
                async with aiohttp.ClientSession() as session:
                    async with session.get(request_url) as request:
                        request_data = await request.json()
                        request_status = request.status

                # Invalid Link
                if request_status == 400:
                    embed = discord.Embed(
                        title="Invalid Link",
                        description="The link entered is not valid. Please ensure you are sending a valid link.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Supported URLs",
                        value="**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.followup.send(embed=embed)
                    raise songlink_exceptions.InvalidLinkException()
                # Unknown Error
                if not (request_status <= 200 or request_status >= 299) or (
                    request_data["linksByPlatform"]["spotify"]["url"] is None
                ):
                    embed = discord.Embed(
                        title="An error has occurred.",
                        description="An error has occurred while searching the URL.\n\n**Solutions:**\n1. Check the URL is a valid song URL.\n2. Try again later.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Supported URLs",
                        value="**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.add_field(
                        name="Error Code from song.link", value=request_status
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.followup.send(embed=embed)
                    raise songlink_exceptions.SongLinkErrorException()
                # Data returned is not song
                elif (
                    request_data["entitiesByUniqueId"][request_data["entityUniqueId"]][
                        "type"
                    ]
                    != "song"
                    and request_data["entitiesByUniqueId"][
                        request_data["entityUniqueId"]
                    ]["type"]
                    != "album"
                ):
                    embed = discord.Embed(
                        title="Unsupported Link Type",
                        description=f"{request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['type'].title()} link types from this service are unsupported.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Supported URLs",
                        value="**Spotify:** Song, Artist, Album, Playlist, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.followup.send(embed=embed)
                    raise songlink_exceptions.UnsupportedDataTypeException()
                # Data valid
                else:
                    url = request_data["linksByPlatform"]["spotify"]["url"]
            # Required platforms not returned from song.link
            except KeyError:
                embed = discord.Embed(
                    title="Error",
                    description="Couldn't find the song on Spotify or your selected streaming service.",
                    color=Color.red(),
                )
                await interaction.followup.send(embed=embed)
                return

            # Set Platform Strings
            if (
                request_data["entitiesByUniqueId"][request_data["entityUniqueId"]][
                    "apiProvider"
                ]
                == "amazon"
            ):
                platform = "Play on Amazon Music"
                platform_api = request_data["entitiesByUniqueId"][
                    request_data["entityUniqueId"]
                ]["apiProvider"]
            elif (
                request_data["entitiesByUniqueId"][request_data["entityUniqueId"]][
                    "apiProvider"
                ]
                == "itunes"
            ):
                platform = "Play on Apple Music"
                platform_api = "appleMusic"
            elif (
                request_data["entitiesByUniqueId"][request_data["entityUniqueId"]][
                    "apiProvider"
                ]
                == "soundcloud"
            ):
                platform = "Play on SoundCloud"
                platform_api = request_data["entitiesByUniqueId"][
                    request_data["entityUniqueId"]
                ]["apiProvider"]
            elif (
                request_data["entitiesByUniqueId"][request_data["entityUniqueId"]][
                    "apiProvider"
                ]
                == "youtube"
            ):
                platform = "Play on YouTube"
                platform_api = request_data["entitiesByUniqueId"][
                    request_data["entityUniqueId"]
                ]["apiProvider"]
            else:
                platform = f"Play on {request_data['entitiesByUniqueId'][request_data['entityUniqueId']]['apiProvider'].title()}"
                platform_api = request_data["entitiesByUniqueId"][
                    request_data["entityUniqueId"]
                ]["apiProvider"]

            # 90 day TTL
            ttl = int(datetime.datetime.now().timestamp()) + 7776000

            async with self.cache_pool.acquire() as sql:
                # Add to cache
                await sql.execute(
                    "INSERT INTO songlinkCache (userURL, spotifyURL, platformRich, platformRaw, ttl) VALUES (?, ?, ?, ?, ?)",
                    (
                        user_url,
                        url,
                        platform,
                        platform_api,
                        ttl,
                    ),
                )
                await sql.commit()

            await self.refresh_cache()

            return url, platform, platform_api

        try:
            # Query song.link if required
            if "spotify" not in url:
                # Check if URL is in cache
                if (
                    url not in [entry[0] for entry in self.cache]
                ) or bypass_cache:  # Not cached
                    async with self.cache_pool.acquire() as sql:
                        # Remove from DB
                        await sql.execute(
                            "DELETE FROM songlinkCache WHERE userURL = ?", (url,)
                        )
                        await sql.commit()

                    await self.refresh_cache()

                    try:
                        embed = discord.Embed(
                            title="Loading...",
                            description=f"{self.bot.options['loading-emoji']} Converting your song link to Spotify to get more info. This will take a few moments; we will let you know if something goes wrong.",
                            color=Color.orange(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.followup.send(
                            embed=embed, ephemeral=ephemeral
                        )

                        url, platform, platform_api = await songlink_request(url)

                        cached = False
                    except Exception:
                        return
                else:  # Cached
                    for entry in self.cache:
                        if (
                            entry[4] >= int(datetime.datetime.now().timestamp())
                            and entry[0] == url
                        ):  # Check TTL is still valid
                            url = entry[1]
                            platform = entry[2]
                            platform_api = entry[3]

                            cached = True

                            break
                        elif entry[0] == url:
                            async with self.cache_pool.acquire() as sql:
                                # Remove from DB
                                await sql.execute(
                                    "DELETE FROM songlinkCache WHERE userURL = ?",
                                    (url,),
                                )
                                await sql.commit()

                            await self.refresh_cache()

                            try:
                                embed = discord.Embed(
                                    title="Loading...",
                                    description=f"{self.bot.options['loading-emoji']} Converting your song link to Spotify to get more info. This will take a few moments; we will let you know if something goes wrong.",
                                    color=Color.orange(),
                                )
                                embed.set_footer(
                                    text=f"@{interaction.user.name}",
                                    icon_url=interaction.user.display_avatar.url,
                                )

                                await interaction.followup.send(
                                    embed=embed, ephemeral=ephemeral
                                )

                                url = self.cleaner.clean(url)
                                url, platform, platform_api = await songlink_request(
                                    url
                                )

                                cached = False
                            except Exception:
                                return
                        else:
                            continue
            else:
                platform = "spotify"
                platform_api = "spotify"

                cached = False

            # Expand spotify.link URL if present
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
                    logging.error(f"[SPOTURL] Error while expanding URL: {error}")

                    if interaction.user.id in self.bot.options["owner-ids"]:
                        embed = discord.Embed(
                            title="Error occurred while expanding URL.",
                            description=error,
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    else:
                        embed = discord.Embed(
                            title="Error occurred while expanding URL.",
                            description="A **spotify.link** was detected, but we could not expand it. Is it valid?\n\nIf you are sure the URL is valid and supported, please try again later or message <@563372552643149825> for assistance.",
                            color=Color.red(),
                        )
                        embed.set_footer(
                            text=f"@{interaction.user.name}",
                            icon_url=interaction.user.display_avatar.url,
                        )
                        await interaction.followup.send(embed=embed)
                        return

            # Track URL
            if "track" in url:
                # Get info and links
                try:
                    result = self.sp.track(url)
                except spotipy.exceptions.SpotifyException:
                    embed = discord.Embed(
                        title="Error",
                        description="A Spotify error occurred. Check the link is valid.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Tip",
                        value="Is there a reigon code in the Spotify URL - e.g. `/intl-de/`? Remove it and it should fix the URL.",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed)

                    return

                # Add OG platform button when OG platform isn't Spotify
                if platform_api != "spotify":
                    await elements.song(
                        self=self,
                        item=result,
                        interaction=interaction,
                        add_button_url=og_url,
                        add_button_text=platform,
                        cached=cached,
                        ephemeral=ephemeral,
                        responded=not (cached),
                    )
                else:
                    await elements.song(
                        self=self,
                        item=result,
                        interaction=interaction,
                        cached=cached,
                        ephemeral=ephemeral,
                    )
            # Artist URL
            elif "artist" in url:
                # Fetch artist info
                try:
                    result_info = self.sp.artist(url)
                except spotipy.exceptions.SpotifyException:
                    embed = discord.Embed(
                        title="Error",
                        description="A Spotify error occurred. Check the link is valid.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Tip",
                        value="Is there a reigon code in the Spotify URL - e.g. `/intl-de/`? Remove it and it should fix the URL.",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed)

                    return

                # Fetch artist top songs
                result_top_tracks = self.sp.artist_top_tracks(url)

                await elements.artist(
                    self=self,
                    item=result_info,
                    top_tracks=result_top_tracks,
                    interaction=interaction,
                    ephemeral=ephemeral,
                )
            # Album URL
            elif "album" in url:
                # Fetch artist info
                try:
                    result_info = self.sp.album(url)
                except spotipy.exceptions.SpotifyException:
                    embed = discord.Embed(
                        title="Error",
                        description="A Spotify error occurred. Check the link is valid.",
                        color=Color.red(),
                    )
                    embed.add_field(
                        name="Tip",
                        value="Is there a reigon code in the Spotify URL - e.g. `/intl-de/`? Remove it and it should fix the URL.",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed)

                    return

                # Add OG platform button when OG platform isn't Spotify
                if platform_api != "spotify":
                    await elements.album(
                        self=self,
                        item=result_info,
                        interaction=interaction,
                        add_button_url=og_url,
                        add_button_text=platform,
                        cached=cached,
                        ephemeral=ephemeral,
                        responded=not (cached),
                    )
                else:
                    await elements.album(
                        self=self,
                        item=result_info,
                        interaction=interaction,
                        cached=cached,
                        ephemeral=ephemeral,
                    )
            # Playlist URL
            elif "playlist" in url:
                # Search playlist on Spotify
                # try:
                result_info = self.sp.playlist(url, market="GB")
                # except spotipy.exceptions.SpotifyException:
                #     embed = discord.Embed(
                #         title="Error",
                #         description="A Spotify error occurred. Check the link is valid.",
                #         color=Color.red(),
                #     )
                #     embed.add_field(
                #         name="Tip",
                #         value="Is there a reigon code in the Spotify URL - e.g. `/intl-de/`? Remove it and it should fix the URL.",
                #     )
                #     embed.set_footer(
                #         text=f"@{interaction.user.name}",
                #         icon_url=interaction.user.display_avatar.url,
                #     )

                #     await interaction.followup.send(embed=embed)

                #     return

                embed = discord.Embed(
                    title="Loading...",
                    description=f"{self.bot.options['loading-emoji']} Getting images...",
                    color=Color.orange(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                webhook = await interaction.followup.send(
                    embed=embed, ephemeral=ephemeral, wait=True
                )

                # Get image URL
                image_url = result_info["images"][0]["url"]

                # Get image, store in memory
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as request:
                        image_data = BytesIO()

                        async for chunk in request.content.iter_chunked(10):
                            image_data.write(chunk)

                        image_data.seek(0)  # Reset buffer position to start

                # Get dominant colour for embed
                color_thief = ColorThief(image_data)
                dominant_color = color_thief.get_color()

                embed = discord.Embed(
                    title="Loading...",
                    description=f"{self.bot.options['loading-emoji']} Parsing info...",
                    color=Color.orange(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.edit_original_response(embed=embed)

                pages = await asyncio.to_thread(
                    _fetch_playlist_items,
                    self,
                    result_info=result_info,
                    url=url,
                )

                # Define page view
                class PlaylistPagesController(View):
                    def __init__(self, pages):
                        super().__init__(timeout=None)

                        self.page = 0
                        self.pages = pages

                        self.locked = False

                        self.user_id: int
                        self.msg_id: int

                        spotify_button = discord.ui.Button(
                            label="Show on Spotify",
                            style=ButtonStyle.url,
                            url=result_info["external_urls"]["spotify"],
                        )
                        self.add_item(spotify_button)

                        for item in self.children:
                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True

                    # Timeout
                    async def on_timeout(self) -> None:
                        try:
                            for item in self.children:
                                item.disabled = True

                            msg = await interaction.channel.fetch_message(self.msg_id)
                            await msg.edit(view=self)
                        except Exception:
                            pass

                    async def interaction_check(self, interaction: discord.Interaction):
                        if interaction.user.id != self.user_id:
                            if self.locked:
                                embed = discord.Embed(
                                    title="Error",
                                    description="This command is locked. Only the owner can control it.",
                                    color=Color.red(),
                                )
                                await interaction.response.send_message(
                                    embed=embed, ephemeral=True
                                )
                            else:
                                return True
                        else:
                            return True

                    @discord.ui.button(
                        emoji="⏮️", style=ButtonStyle.red, custom_id="first"
                    )
                    async def first_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        self.page = 0

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "first" or item.custom_id == "prev":
                                item.disabled = True

                        embed = discord.Embed(
                            title=f"{result_info['name']} (Playlist)",
                            description=f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                        embed.set_thumbnail(url=result_info["images"][0]["url"])
                        embed.set_footer(
                            text=f"@{interaction.user.name} • Page {self.page + 1}/{len(pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="⏪", style=ButtonStyle.gray, custom_id="prev"
                    )
                    async def prev_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        if self.page - 1 == 0:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False

                                if (
                                    item.custom_id == "first"
                                    or item.custom_id == "prev"
                                ):
                                    item.disabled = True
                        else:
                            self.page -= 1

                            for item in self.children:
                                item.disabled = False

                        embed = discord.Embed(
                            title=f"{result_info['name']} (Playlist)",
                            description=f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                        embed.set_thumbnail(url=result_info["images"][0]["url"])
                        embed.set_footer(
                            text=f"@{interaction.user.name} • Page {self.page + 1}/{len(pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="🔓", style=ButtonStyle.green, custom_id="lock"
                    )
                    async def lock_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        if interaction.user.id == self.user_id:
                            self.locked = not self.locked

                            if self.locked:
                                button.emoji = "🔒"
                                button.style = ButtonStyle.red
                            else:
                                button.emoji = "🔓"
                                button.style = ButtonStyle.green

                            await interaction.response.edit_message(view=self)
                        else:
                            embed = discord.Embed(
                                title="Error",
                                description="Only the command runner can toggle the page controls lock.",
                                color=Color.red(),
                            )
                            await interaction.response.send_message(
                                embed=embed, ephemeral=True
                            )

                    @discord.ui.button(
                        emoji="⏩", style=ButtonStyle.gray, custom_id="next"
                    )
                    async def next_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        if (self.page + 1) == (len(self.pages) - 1):
                            self.page += 1

                            for item in self.children:
                                item.disabled = False

                                if item.custom_id == "next" or item.custom_id == "last":
                                    item.disabled = True
                        else:
                            self.page += 1

                            for item in self.children:
                                item.disabled = False

                        embed = discord.Embed(
                            title=f"{result_info['name']} (Playlist)",
                            description=f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                        embed.set_thumbnail(url=result_info["images"][0]["url"])
                        embed.set_footer(
                            text=f"@{interaction.user.name} • Page {self.page + 1}/{len(pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                    @discord.ui.button(
                        emoji="⏭️", style=ButtonStyle.green, custom_id="last"
                    )
                    async def last_button(
                        self,
                        interaction: discord.Interaction,
                        button: discord.ui.Button,
                    ):
                        self.page = len(self.pages) - 1

                        for item in self.children:
                            item.disabled = False

                            if item.custom_id == "next" or item.custom_id == "last":
                                item.disabled = True

                        embed = discord.Embed(
                            title=f"{result_info['name']} (Playlist)",
                            description=f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{self.pages[self.page]}",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                        embed.set_thumbnail(url=result_info["images"][0]["url"])
                        embed.set_footer(
                            text=f"@{interaction.user.name} • Page {self.page + 1}/{len(pages)}",
                            icon_url=interaction.user.display_avatar.url,
                        )

                        await interaction.response.edit_message(embed=embed, view=self)

                embed = discord.Embed(
                    title=f"{result_info['name']} (Playlist)",
                    description=f"by {result_info['owner']['display_name']} - {result_info['tracks']['total']} items\n\n{pages[0]}",
                    color=Color.from_rgb(
                        r=dominant_color[0], g=dominant_color[1], b=dominant_color[2]
                    ),
                )

                embed.set_thumbnail(url=result_info["images"][0]["url"])
                embed.set_footer(
                    text=f"@{interaction.user.name} • Page 1/{len(pages)}",
                    icon_url=interaction.user.display_avatar.url,
                )

                # If there's only 1 page, make embed without page buttons
                if len(pages) == 1:
                    # Add Open in Spotify button
                    view = View()
                    spotify_button = discord.ui.Button(
                        label="Show on Spotify",
                        style=ButtonStyle.url,
                        url=result_info["external_urls"]["spotify"],
                    )
                    view.add_item(spotify_button)

                    await interaction.edit_original_response(embed=embed, view=view)
                # Else, make embed with page buttons
                else:
                    playlist_pages_controller = PlaylistPagesController(pages)
                    webhook = await interaction.edit_original_response(
                        embed=embed, view=playlist_pages_controller
                    )

                    playlist_pages_controller.msg_id = webhook.id
                    playlist_pages_controller.user_id = interaction.user.id
        except KeyError:
            embed = discord.Embed(
                title="Error",
                description="Couldn't find the song on Spotify or your selected streaming service.",
                color=Color.red(),
            )
            await interaction.edit_original_response(embed=embed)
            return


async def setup(bot):
    # Only load if Spotify API keys are present
    try:
        if (
            bot.tokens["spotify-api-id"] is not None
            and bot.tokens["spotify-api-secret"] is not None
        ):
            if (
                bot.tokens["spotify-api-id"] != ""
                and bot.tokens["spotify-api-secret"] != ""
            ):
                await bot.add_cog(SongURL(bot))
    except KeyError:
        pass
