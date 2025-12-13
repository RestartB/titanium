from textwrap import shorten
from typing import Optional
from urllib.parse import quote, quote_plus

import aiohttp
import discord
from discord import ButtonStyle, Color, Embed, Interaction, InteractionMessage, WebhookMessage
from discord.ui import Button, Select, View, button

from lib.views.pagination import PaginationView


class SongView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
        add_button_url: Optional[str] = None,
        add_button_text: Optional[str] = None,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.item = item
        self.colours = colours
        self.add_button_url = add_button_url
        self.add_button_text = add_button_text

        # Calculate duration
        seconds, item["duration_ms"] = divmod(item["duration_ms"], 1000)
        minutes, seconds = divmod(seconds, 60)

        # Add Open in Spotify button
        spotify_button = Button(
            label=f"Play on Spotify ({int(minutes):02d}:{int(seconds):02d})",
            style=ButtonStyle.url,
            url=item["external_urls"]["spotify"],
        )
        self.add_item(spotify_button)

    @button(label="Menu", style=ButtonStyle.gray)
    async def menu(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        view = SongMenuView(
            item=self.item,
            colours=self.colours,
            add_button_url=self.add_button_url,
            add_button_text=self.add_button_text,
        )

        view.message = await interaction.followup.send(view=view, ephemeral=True, wait=True)


class SongMenuView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
        add_button_url: Optional[str] = None,
        add_button_text: Optional[str] = None,
    ):
        super().__init__()

        self.item = item
        self.colours = colours
        self.message: WebhookMessage

        # Add additional button if provided
        if not (add_button_url is None or add_button_text is None):
            add_button = Button(
                label=add_button_text,
                style=ButtonStyle.url,
                url=add_button_url,
                row=0,
            )

            self.add_item(add_button)

        # Add song.link button
        songlink_button = Button(
            label="Other Streaming Services",
            style=ButtonStyle.url,
            url=f"https://song.link/{item['external_urls']['spotify']}",
            row=0,
        )

        self.add_item(songlink_button)

        # Add Search on Google button
        google_button = Button(
            label="Search on Google",
            style=ButtonStyle.url,
            url=f"https://www.google.com/search?q={quote_plus(item['name'])}",
            row=0,
        )

        self.add_item(google_button)

    async def on_timeout(self):
        await self.message.delete()

    @button(label="Album Art", style=ButtonStyle.gray)
    async def art(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.item["album"]["images"] is not None:
            if (
                self.item["album"]["images"][0]["height"] is None
                or self.item["album"]["images"][0]["width"] is None
            ):
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['album']['images'][0]['width']}x{self.item['album']['images'][0]['height']})"

            embed = Embed(
                title=f"{self.item['name']} - Album Art",
                description=description,
                color=Color.from_rgb(r=self.colours[0], g=self.colours[1], b=self.colours[2]),
            )

            embed.set_image(url=self.item["album"]["images"][0]["url"])

            view = View()
            view.add_item(
                Button(
                    label="Open in Browser",
                    style=ButtonStyle.url,
                    url=self.item["album"]["images"][0]["url"],
                )
            )

            await interaction.edit_original_response(embed=embed, view=view)
        else:
            embed = Embed(title="No album art available.", color=Color.red())
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=embed)

        self.stop()

    @button(label="Lyrics", style=ButtonStyle.gray)
    async def lyrics(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        url = f"https://lrclib.net/api/search?track_name={quote(self.item['name'])}&artist_name={quote(self.item['artists'][0]['name'])}"
        headers = {"User-Agent": "Titanium Discord Bot (https://titaniumbot.me)"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data != []:
                        selector = SongLyricSelection(item=self.item)
                        for lyric_data in data:
                            selector.add_option(
                                label=shorten(lyric_data["name"], width=100, placeholder="..."),
                                value=lyric_data["id"],
                                description=shorten(
                                    f"{lyric_data['artistName']} - {lyric_data['albumName']}",
                                    width=100,
                                    placeholder="...",
                                ),
                            )

                        view = SongLyricsSelectionView()
                        view.add_item(selector)
                        await interaction.edit_original_response(view=view)

                        view.message = await interaction.original_response()
                    else:
                        embed = Embed(
                            title="No Lyrics Found",
                            description="No lyrics were found for this song.",
                            color=Color.red(),
                        )
                        await interaction.edit_original_response(embed=embed)
                else:
                    embed = Embed(
                        title="Error",
                        description="Failed to fetch lyrics. Please try again later.",
                        color=Color.red(),
                    )
                    await interaction.edit_original_response(embed=embed)

        self.stop()


class SongLyricSelection(Select):
    def __init__(self, item: dict):
        super().__init__(
            placeholder="Select a song",
            min_values=1,
            max_values=1,
        )

        self.item = item

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        if self.view:
            self.view.stop()

        request_url = f"https://lrclib.net/api/get/{self.values[0]}"

        async with aiohttp.ClientSession() as session:
            async with session.get(request_url) as response:
                if response.status == 200:
                    selected_song_data = await response.json()
                else:
                    embed = Embed(
                        title="Error",
                        description="Failed to fetch lyrics. Please try again later.",
                        color=Color.red(),
                    )
                    await interaction.edit_original_response(embed=embed)
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

            embed_pages: list[discord.Embed] = []
            for page in lyrics:
                embed = discord.Embed(
                    title=f"{selected_song_data['name']}",
                    description=page,
                    color=Color.random(),
                )
                embed.set_author(
                    name=f"{selected_song_data['artistName']} - lrclib.net",
                )

                embed_pages.append(embed)

        embed_pages[0].set_footer(
            text=f"Controlling: @{interaction.user.name}"
            if len(embed_pages) > 1
            else f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        if len(embed_pages) > 1:
            view = PaginationView(
                embeds=embed_pages,
                timeout=300,
            )

        await interaction.edit_original_response(embed=embed_pages[0], view=view)


class SongLyricsSelectionView(View):
    def __init__(self):
        super().__init__(timeout=900)

        self.message: InteractionMessage

    async def on_timeout(self):
        await self.message.delete()


class ArtistView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
        op_id: int,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.item = item
        self.colours = colours
        self.op_id = op_id

        # Add Open in Spotify button
        spotify_button = Button(
            label="Play on Spotify",
            style=ButtonStyle.url,
            url=item["external_urls"]["spotify"],
        )
        self.add_item(spotify_button)

    @button(label="Menu", style=ButtonStyle.gray)
    async def menu(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        view = ArtistMenuView(
            item=self.item,
            colours=self.colours,
        )

        view.message = await interaction.followup.send(view=view, ephemeral=True, wait=True)


class ArtistMenuView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
    ):
        super().__init__()

        self.item = item
        self.colours = colours
        self.message: discord.WebhookMessage

        # Add Search on Google button
        google_button = Button(
            label="Search on Google",
            style=ButtonStyle.url,
            url=f"https://www.google.com/search?q={quote_plus(item['name'])}",
        )
        self.add_item(google_button)

    async def on_timeout(self):
        await self.message.delete()

    @button(label="Icon", style=ButtonStyle.gray)
    async def art(self, interaction: Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        if self.item["images"] is not None:
            if self.item["images"][0]["height"] is None or self.item["images"][0]["width"] is None:
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['images'][0]['width']}x{self.item['images'][0]['height']})"

            embed = Embed(
                title=f"{self.item['name']} - Icon",
                description=description,
                color=Color.from_rgb(r=self.colours[0], g=self.colours[1], b=self.colours[2]),
            )

            embed.set_image(url=self.item["images"][0]["url"])

            view = View()
            view.add_item(
                Button(
                    label="Open in Browser",
                    style=ButtonStyle.url,
                    url=self.item["images"][0]["url"],
                )
            )

            await interaction.edit_original_response(embed=embed, view=view)
        else:
            embed = Embed(title="No icon available.", color=Color.red())
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=embed)

        self.stop()


class AlbumMenuButton(discord.ui.Button):
    def __init__(
        self,
        item: dict,
        artists: str,
        artist_img: str,
        colours: list,
        add_button_url: Optional[str] = None,
        add_button_text: Optional[str] = None,
    ):
        super().__init__(label="Menu", style=discord.ButtonStyle.gray, row=1)

        self.item = item
        self.artists = artists
        self.artist_img = artist_img
        self.colours = colours
        self.add_button_url = add_button_url
        self.add_button_text = add_button_text

    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AlbumMenuView(
            item=self.item,
            artists=self.artists,
            artist_img=self.artist_img,
            colours=self.colours,
            add_button_url=self.add_button_url,
            add_button_text=self.add_button_text,
        )

        view.message = await interaction.followup.send(view=view, ephemeral=True, wait=True)


class AlbumMenuView(View):
    def __init__(
        self,
        item: dict,
        artists: str,
        artist_img: str,
        colours: list,
        add_button_url: Optional[str] = None,
        add_button_text: Optional[str] = None,
    ):
        super().__init__()

        self.item = item
        self.artists = artists
        self.artist_img = artist_img
        self.colours = colours
        self.message: discord.WebhookMessage

        self.page = 0
        self.locked = False

        if not (add_button_url is None or add_button_text is None):
            # Add additional button
            add_button = discord.ui.Button(
                label=add_button_text,
                style=discord.ButtonStyle.url,
                url=add_button_url,
                row=0,
            )
            self.add_item(add_button)

        # Add song.link button
        songlink_button = discord.ui.Button(
            label="Other Streaming Services",
            style=discord.ButtonStyle.url,
            url=f"https://song.link/{item['external_urls']['spotify']}",
            row=0,
        )
        self.add_item(songlink_button)

        # Add Search on Google button
        google_button = discord.ui.Button(
            label="Search on Google",
            style=discord.ButtonStyle.url,
            url=f"https://www.google.com/search?q={quote_plus(item['name'])}+{quote_plus(artists)}",
            row=0,
        )
        self.add_item(google_button)

    async def on_timeout(self):
        await self.message.delete()

    @discord.ui.button(label="Album Art", style=discord.ButtonStyle.gray, row=1)
    async def art(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if self.item["images"] is not None:
            if self.item["images"][0]["height"] is None or self.item["images"][0]["width"] is None:
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['images'][0]['width']}x{self.item['images'][0]['height']})"

            embed = discord.Embed(
                title=f"{self.item['name']} - Album Art",
                description=description,
                color=Color.from_rgb(r=self.colours[0], g=self.colours[1], b=self.colours[2]),
            )

            embed.set_author(
                name=self.artists,
                url=self.item["artists"][0]["external_urls"]["spotify"],
                icon_url=self.artist_img,
            )

            embed.set_image(url=self.item["images"][0]["url"])

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Open in Browser",
                    style=discord.ButtonStyle.url,
                    url=self.item["images"][0]["url"],
                )
            )

            await interaction.edit_original_response(embed=embed, view=view)
        else:
            embed = discord.Embed(title="No album art available.", color=Color.red())
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=embed)

        self.stop()
