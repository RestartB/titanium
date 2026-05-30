from textwrap import shorten

import discord
import spotipy
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import Select, View
from discord.utils import escape_markdown
from spotipy.oauth2 import SpotifyClientCredentials

import utils.spotify_elements as elements


class SpotifySearch(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(
            client_id=self.bot.tokens["spotify-api-id"],
            client_secret=self.bot.tokens["spotify-api-secret"],
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    searchGroup = app_commands.Group(
        name="search",
        description="Search for something on Spotify.",
    )

    async def song_search_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        # Strip whitespace, cap at 100 characters
        current = current.strip()[:100]

        if current and current != "":
            # Check if search is Spotify ID
            if len(current) == 22 and " " not in current:
                try:
                    item = self.sp.track(current)

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

                    album = shorten(
                        text=item["album"]["name"], width=22, placeholder="..."
                    )

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
                options = [
                    app_commands.Choice(
                        name="Spotify error, send command now to search again",
                        value=current,
                    )
                ]

            if len(result["tracks"]["items"]) == 0:
                options = [
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

                    album = shorten(
                        text=item["album"]["name"], width=22, placeholder="..."
                    )

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
    @searchGroup.command(name="song", description="Search for a song on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=song_search_autocomplete)
    async def spotify_song_search(
        self,
        interaction: discord.Interaction,
        search: app_commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title="Error",
                description="No search term provided.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.track(search)

                await elements.song(
                    self=self,
                    item=item,
                    interaction=interaction,
                    ephemeral=ephemeral,
                )

                return
            except spotipy.exceptions.SpotifyException:
                pass

        # Search Spotify
        result = self.sp.search(search, type="track", limit=10)

        # Check if result is blank
        if len(result["tracks"]["items"]) == 0:
            embed = discord.Embed(
                title="Error",
                description="No results were found.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
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
                    description = (
                        f"{artist_string} - {item['album']['name']}"[:97] + "..."
                    )
                else:
                    description = f"{artist_string} - {item['album']['name']}"

                options_list.append(
                    discord.SelectOption(label=label, description=description, value=i)
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
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                # Find unique ID of selection in the list
                item = result["tracks"]["items"][int(select.values[0])]

                await elements.song(
                    self=self,
                    item=item,
                    interaction=interaction,
                    ephemeral=ephemeral,
                    responded=True,
                )

        # Set up list with provided values
        select.callback = response
        view = View()
        view.add_item(select)

        # Edit initial message to show dropdown
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

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

                    options = [
                        app_commands.Choice(
                            name="Spotify ID detected, send command now to get info",
                            value=current,
                        )
                    ]

                    options.append(
                        app_commands.Choice(
                            name=shorten(
                                text=item["name"], width=100, placeholder="..."
                            ),
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
            except spotipy.exceptions.SpotifyException:
                options = [
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
                            name=shorten(
                                text=item["name"], width=100, placeholder="..."
                            ),
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
    @searchGroup.command(name="artist", description="Search for an artist on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=artist_search_autocomplete)
    async def spotify_artist_search(
        self,
        interaction: discord.Interaction,
        search: app_commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title="Error",
                description="No search term provided.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.artist(search)
                top_tracks = self.sp.artist_top_tracks(item["id"])

                await elements.artist(
                    self=self,
                    item=item,
                    top_tracks=top_tracks,
                    interaction=interaction,
                    ephemeral=ephemeral,
                )

                return
            except spotipy.exceptions.SpotifyException:
                pass

        # Search Spotify
        result = self.sp.search(search, type="artist", limit=10)

        # Check if result is blank
        if len(result["artists"]["items"]) == 0:
            embed = discord.Embed(
                title="Error",
                description="No results were found.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        else:
            # Sort through request data
            i = 0
            for item in result["artists"]["items"]:
                if len(item["name"]) > 100:
                    title = item["name"][:97] + "..."
                else:
                    title = item["name"]

                options_list.append(discord.SelectOption(label=title, value=i))
                i += 1

            # Define options
            select = Select(options=options_list)

            embed = discord.Embed(
                title="Select Artist",
                description=f'Showing {len(result["artists"]["items"])} results for "{search}"',
                color=Color.random(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                item = result["artists"]["items"][int(select.values[0])]

                result_info = self.sp.artist(item["id"])

                result_top_tracks = self.sp.artist_top_tracks(item["id"])

                await elements.artist(
                    self=self,
                    item=result_info,
                    top_tracks=result_top_tracks,
                    interaction=interaction,
                    ephemeral=ephemeral,
                    responded=True,
                )

            # Set up list with provided values
            select.callback = response
            view = View()
            view.add_item(select)

            # Edit initial message to show dropdown
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

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

                    artists = shorten(
                        text=", ".join(artists_list), width=32, placeholder="..."
                    )

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
            except spotipy.exceptions.SpotifyException:
                options = [
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

                    artists = shorten(
                        text=", ".join(artists_list), width=32, placeholder="..."
                    )

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
    @searchGroup.command(name="album", description="Search for an album on Spotify.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(
        search="What you are searching for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(search=album_search_autocomplete)
    async def spotify_album_search(
        self,
        interaction: discord.Interaction,
        search: app_commands.Range[str, 0, 100],
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        search = search.strip()
        options_list = []

        if not search or search == "":
            embed = discord.Embed(
                title="Error",
                description="No search term provided.",
                color=Color.red(),
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        # Check if search is Spotify ID
        if len(search) == 22 and " " not in search:
            try:
                item = self.sp.album(search)

                await elements.album(
                    self=self,
                    item=item,
                    interaction=interaction,
                    ephemeral=ephemeral,
                )

                return
            except spotipy.exceptions.SpotifyException:
                pass

        # Search Spotify
        result = self.sp.search(search, type="album", limit=10)

        # Check if result is blank
        if len(result["albums"]["items"]) == 0:
            embed = discord.Embed(
                title="Error",
                description="No results were found.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed)
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
                    discord.SelectOption(label=title, description=description, value=i)
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
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            # Response to user selection
            async def response(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=ephemeral)

                item = result["albums"]["items"][int(select.values[0])]

                result_info = self.sp.album(item["id"])

                await elements.album(
                    self=self,
                    item=result_info,
                    interaction=interaction,
                    ephemeral=ephemeral,
                    responded=True,
                )

            # Set up list with provided values
            select.callback = response
            view = View()
            view.add_item(select)

            # Edit initial message to show dropdown
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot):
    pass
