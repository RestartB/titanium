import logging
from io import BytesIO

import aiohttp
import discord
import spotipy
from colorthief import ColorThief
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(
            client_id=self.bot.tokens["spotify-api-id"],
            client_secret=self.bot.tokens["spotify-api-secret"],
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    # Spotify Image command
    @app_commands.command(
        name="image", description="Get high quality album art from a Spotify URL."
    )
    @app_commands.describe(
        url="The target Spotify URL. Song, album, playlist and spotify.link URLs are supported.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def spotify_image(
        self, interaction: discord.Interaction, url: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

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
                logging.error("[SPOTIMG] Error while expanding URL.")
                logging.error(error)
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
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
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
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                    return

        embed = discord.Embed(
            title="Loading...",
            description=f"{self.bot.options['loading-emoji']} Getting images...",
            color=Color.orange(),
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

        artist_string = ""

        try:
            if "track" in url:
                result = self.sp.track(url)

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
                            title=f"{result['name']} ({artist_string}) - Album Art",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string}) - Album Art",
                            description=f"Viewing highest quality ({result['album']['images'][0]['width']}x{result['album']['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )

                    embed.set_image(url=result["album"]["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Open in Browser",
                            style=discord.ButtonStyle.url,
                            url=result["album"]["images"][0]["url"],
                        )
                    )

                    await interaction.edit_original_response(embed=embed, view=view)
                else:
                    embed = discord.Embed(
                        title="No album art available.", color=Color.red()
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
            elif "album" in url:
                result = self.sp.album(url)

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
                            title=f"{result['name']} ({artist_string}) - Album Art",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} ({artist_string}) - Album Art",
                            description=f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    embed.set_image(url=result["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Download",
                            style=discord.ButtonStyle.url,
                            url=result["images"][0]["url"],
                        )
                    )

                    await interaction.edit_original_response(embed=embed, view=view)
                else:
                    embed = discord.Embed(
                        title="No album art available.", color=Color.red()
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
            # Playlist URL
            elif "playlist" in url:
                # Search playlist on Spotify
                result = self.sp.playlist(url, market="GB")

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
                            title=f"{result['name']} - {result['owner']['display_name']} (Playlist) - Cover Art",
                            description="Viewing highest quality (Resolution unknown)",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    else:
                        embed = discord.Embed(
                            title=f"{result['name']} - {result['owner']['display_name']} (Playlist) - Cover Art",
                            description=f"Viewing highest quality ({result['images'][0]['width']}x{result['images'][0]['height']})",
                            color=Color.from_rgb(
                                r=dominant_color[0],
                                g=dominant_color[1],
                                b=dominant_color[2],
                            ),
                        )
                    embed.set_image(url=result["images"][0]["url"])
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    view = View()
                    view.add_item(
                        discord.ui.Button(
                            label="Download",
                            style=discord.ButtonStyle.url,
                            url=result["images"][0]["url"],
                        )
                    )

                    await interaction.edit_original_response(embed=embed, view=view)
                else:
                    embed = discord.Embed(
                        title="No cover art available.", color=Color.red()
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.edit_original_response(embed=embed)
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Error while searching URL. Is it a valid and supported Spotify URL?",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )
                await interaction.edit_original_response(embed=embed)
        except spotipy.exceptions.SpotifyException:
            embed = discord.Embed(
                title="Error",
                description="Error while searching URL. Is it a valid and supported Spotify URL?",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=embed)


async def setup(bot):
    pass
