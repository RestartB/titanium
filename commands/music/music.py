from textwrap import shorten
from urllib.parse import quote

import aiohttp
import discord
import spotipy
from discord import ButtonStyle, Color, app_commands
from discord.ext import commands
from discord.ui import View
from spotipy.oauth2 import SpotifyClientCredentials


class SongLyricSelection(discord.ui.Select):
    def __init__(self, data: list[dict], private: bool):
        super().__init__(
            placeholder="Select a song",
            min_values=1,
            max_values=1,
        )

        self.data = data
        self.private = private

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=self.private)

        self.view.stop()
        selected_song = self.values[0]

        selected_song_data = None
        for item in self.data:
            if str(item["id"]) == selected_song:
                selected_song_data = item
                break

        if not selected_song_data:
            embed = discord.Embed(
                title="Error",
                description="Selected song not found.",
                color=Color.red(),
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return

        raw_lyrics: str = selected_song_data["plainLyrics"]

        lyrics_paragraphs = raw_lyrics.split("\n\n")
        lyrics = []
        current_page = ""

        for paragraph in lyrics_paragraphs:
            for line in paragraph.splitlines():
                if (len(current_page)) >= 1024 or len(current_page.splitlines()) >= 30:
                    if current_page:
                        lyrics.append(current_page.strip())
                        current_page = ""

                current_page += f"{line}\n"

            if current_page:
                current_page += "\n"

        if current_page:
            lyrics.append(current_page.strip())

        view = SongLyricsView(
            pages=lyrics,
            private=self.private,
            creator_id=interaction.user.id,
            info=selected_song_data,
        )

        embed = await view._create_embed(0, interaction)
        await interaction.edit_original_response(embed=embed, view=view)


class SongLyricsSelectionView(View):
    def __init__(self):
        super().__init__(timeout=900)

        self.message: discord.InteractionMessage

    async def on_timeout(self):
        await self.message.delete()


class SongLyricsView(View):
    def __init__(
        self,
        pages: list,
        private: bool,
        creator_id: int,
        info: dict,
    ):
        super().__init__(timeout=900)

        self.pages = pages
        self.page = 0
        self.locked = False
        self.info = info

        self.private = private
        self.creator_id = creator_id

        for item in self.children:
            if item.custom_id == "first" or item.custom_id == "prev":
                item.disabled = True
            elif (item.custom_id == "next" or item.custom_id == "last") and len(
                self.pages
            ) <= 1:
                item.disabled = True
            elif item.custom_id == "lock" and self.private:
                self.remove_item(item)

    async def _create_embed(self, page: int, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"{self.info['name']} - Lyrics",
            description=self.pages[page],
            color=Color.random(),
        )

        embed.set_footer(
            text=f"@{interaction.user.name} • Page {page + 1}/{len(self.pages)} • lrclib.net",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_author(
            name=f"{self.info['artistName']}",
        )

        return embed

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            if self.locked:
                embed = discord.Embed(
                    title="Error",
                    description="This command is locked. Only the owner can control it.",
                    color=Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                return True
        else:
            return True

    @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first")
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

        embed = await self._create_embed(self.page, interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev")
    async def prev_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if self.page - 1 == 0:
            self.page -= 1

            for item in self.children:
                item.disabled = False

                if item.custom_id == "first" or item.custom_id == "prev":
                    item.disabled = True
        else:
            self.page -= 1

            for item in self.children:
                item.disabled = False

        embed = await self._create_embed(self.page, interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock")
    async def lock_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id == self.creator_id:
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
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next")
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

        embed = await self._create_embed(self.page, interaction)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last")
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

        embed = await self._create_embed(self.page, interaction)
        await interaction.response.edit_message(embed=embed, view=self)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_manager = SpotifyClientCredentials(
            client_id=self.bot.tokens["spotify-api-id"],
            client_secret=self.bot.tokens["spotify-api-secret"],
        )
        self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

    # Lyrics command
    @app_commands.command(name="lyrics", description="Find Lyrics to a song.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        search="The song you're seaching for. Can be a search term or Spotify song link.",
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 10)
    async def lyrics(
        self,
        interaction: discord.Interaction,
        search: str,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        search_link = search.lstrip().lstrip("https://").lstrip("http://").lstrip("/")
        url = ""

        if search_link.startswith("open.spotify.com/track/"):
            try:
                item = self.sp.track(f"https://{search_link}")
                url = f"https://lrclib.net/api/search?track_name={quote(item['name'])}&artist_name={quote(item['artists'][0]['name'])}"
            except spotipy.exceptions.SpotifyException:
                pass

        if url == "":
            url = f"https://lrclib.net/api/search?track_name={quote(search)}"

        headers = {"User-Agent": "Titanium Discord Bot (https://titaniumbot.me)"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    embed = discord.Embed(
                        title="Error",
                        description="Failed to fetch lyrics. Please try again later.",
                        color=Color.red(),
                    )
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)

                data = await response.json()

        if not data or data == []:
            embed = discord.Embed(
                title="No Results Found",
                description="No lyrics found for the provided song.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        view = SongLyricsSelectionView()
        selection = SongLyricSelection(data=data, private=ephemeral)

        for item in data:
            selection.add_option(
                label=shorten(item["name"], width=100, placeholder="..."),
                value=item["id"],
                description=shorten(
                    f"{item['artistName']} - {item['albumName']}",
                    width=100,
                    placeholder="...",
                ),
            )

        view.add_item(selection)
        embed = discord.Embed(
            title="Select song",
            description=f"Found {len(data)} results. Please select a song from the dropdown below.",
            color=Color.random(),
        )
        embed.set_footer(
            text=f"@{interaction.user.name} • lrclib.net",
            icon_url=interaction.user.display_avatar.url,
        )
        view.message = await interaction.followup.send(
            embed=embed, view=view, ephemeral=ephemeral, wait=True
        )


async def setup(bot):
    await bot.add_cog(Music(bot))
