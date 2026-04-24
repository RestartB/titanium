import datetime
import logging
from urllib.parse import quote

import aiohttp
import asqlite
import discord
import spotipy
from discord import Color, app_commands
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials
from url_cleaner import UrlCleaner

import utils.songlink_exceptions as songlink_exceptions
import utils.spotify_elements as elements


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
    @app_commands.describe(url="The target URL.")
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

        sent_message = False
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
                        value="**Spotify:** Song, Artist, Album, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
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
                        value="**Spotify:** Song, Artist, Album, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.add_field(
                        name="Error Code from song.link", value=request_status
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
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
                        value="**Spotify:** Song, Artist, Album, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - Assisted by song.link",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
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
                await interaction.edit_original_response(embed=embed)
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
                        sent_message = True

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
                                sent_message = True

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

                        if sent_message:
                            return await interaction.edit_original_response(embed=embed)
                        return await interaction.followup.send(embed=embed)
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

                        if sent_message:
                            return await interaction.edit_original_response(embed=embed)
                        return await interaction.followup.send(embed=embed)

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
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    if sent_message:
                        return await interaction.edit_original_response(embed=embed)
                    return await interaction.followup.send(embed=embed)

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

                    if sent_message:
                        return await interaction.edit_original_response(embed=embed)
                    return await interaction.followup.send(embed=embed)

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
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    if sent_message:
                        return await interaction.edit_original_response(embed=embed)
                    return await interaction.followup.send(embed=embed)

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
                embed = discord.Embed(
                    title="Playlists Not Supported",
                    description="Due to new Spotify restrictions, playlists are no longer supported.",
                    color=Color.red(),
                )
                embed.add_field(
                    name="Supported URLs",
                    value="**Spotify:** Song, Artist, Album, `spotify.link`\n**Others (Apple Music, Amazon Music, etc.):** Song, Album",
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                if sent_message:
                    return await interaction.edit_original_response(embed=embed)
                return await interaction.followup.send(embed=embed)
        except KeyError:
            embed = discord.Embed(
                title="Error",
                description="Couldn't find the song on Spotify or your selected streaming service.",
                color=Color.red(),
            )

            if sent_message:
                return await interaction.edit_original_response(embed=embed)
            return await interaction.followup.send(embed=embed)


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
