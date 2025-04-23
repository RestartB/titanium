from io import BytesIO
from urllib.parse import quote_plus

import aiohttp
import discord
from colorthief import ColorThief
from discord import ButtonStyle, Color
from discord.ui import View
from discord.utils import escape_markdown

from utils.truncate import truncate

# --- Song Classes and Functions ---


class SongView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
        add_button_url: str = None,
        add_button_text: str = None,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.item = item
        self.colours = colours
        self.add_button_url = add_button_url
        self.add_button_text = add_button_text

        # Add Open in Spotify button
        spotify_button = discord.ui.Button(
            label="Play on Spotify",
            style=discord.ButtonStyle.url,
            url=item["external_urls"]["spotify"],
        )
        self.add_item(spotify_button)

    @discord.ui.button(label="Menu", style=discord.ButtonStyle.gray)
    async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        view = SongMenuView(
            item=self.item,
            colours=self.colours,
            add_button_url=self.add_button_url,
            add_button_text=self.add_button_text,
        )

        view.message = await interaction.followup.send(
            view=view, ephemeral=True, wait=True
        )


class SongMenuView(View):
    def __init__(
        self,
        item: dict,
        colours: list,
        add_button_url: str = None,
        add_button_text: str = None,
    ):
        super().__init__()

        self.item = item
        self.colours = colours
        self.message: discord.WebhookMessage

        # Add additional button if provided
        if not (add_button_url is None or add_button_text is None):
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
            url=f"https://www.google.com/search?q={quote_plus(item['name'])}",
            row=0,
        )

        self.add_item(google_button)

    async def on_timeout(self):
        await self.message.delete()

    @discord.ui.button(label="Album Art", style=discord.ButtonStyle.gray)
    async def art(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if self.item["album"]["images"] is not None:
            if (
                self.item["album"]["images"][0]["height"] is None
                or self.item["album"]["images"][0]["width"] is None
            ):
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['album']['images'][0]['width']}x{self.item['album']['images'][0]['height']})"

            embed = discord.Embed(
                title=f"{self.item['name']} - Album Art",
                description=description,
                color=Color.from_rgb(
                    r=self.colours[0], g=self.colours[1], b=self.colours[2]
                ),
            )

            embed.set_image(url=self.item["album"]["images"][0]["url"])

            view = View()
            view.add_item(
                discord.ui.Button(
                    label="Open in Browser",
                    style=discord.ButtonStyle.url,
                    url=self.item["album"]["images"][0]["url"],
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


# Song element function
async def song(
    self,
    item: dict,
    interaction: discord.Interaction,
    add_button_url: str = None,
    add_button_text: str = None,
    cached: bool = False,
    ephemeral: bool = False,
    responded: bool = False,
):
    """
    Handle Spotify song embeds.
    """

    artist_img = self.sp.artist(item["artists"][0]["external_urls"]["spotify"])[
        "images"
    ][0]["url"]

    artist_string = ""
    for artist in item["artists"]:
        if artist_string == "":
            artist_string = artist["name"]
        else:
            artist_string += f", {artist['name']}"

    explicit = item["explicit"]

    # Set up new embed
    embed = discord.Embed(
        title=f"{item['name']}{f' {self.bot.options["explicit-emoji"]}' if explicit else ''}",
        description=f"on **[{escape_markdown(item['album']['name'])}](<{item['album']['external_urls']['spotify']}>) • {item['album']['release_date'].split('-', 1)[0]}**",
    )

    embed.set_thumbnail(url=item["album"]["images"][0]["url"])
    embed.set_author(
        name=artist_string,
        url=item["artists"][0]["external_urls"]["spotify"],
        icon_url=artist_img,
    )
    embed.set_footer(
        text=f"@{interaction.user.name}{' • Cached Result' if cached else ''}",
        icon_url=interaction.user.display_avatar.url,
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

    if responded:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


# --- Artist Classes and Functions ---


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
        spotify_button = discord.ui.Button(
            label="Play on Spotify",
            style=discord.ButtonStyle.url,
            url=item["external_urls"]["spotify"],
        )
        self.add_item(spotify_button)

    @discord.ui.button(label="Menu", style=discord.ButtonStyle.gray)
    async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        view = ArtistMenuView(
            item=self.item,
            colours=self.colours,
        )

        view.message = await interaction.followup.send(
            view=view, ephemeral=True, wait=True
        )


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
        google_button = discord.ui.Button(
            label="Search on Google",
            style=discord.ButtonStyle.url,
            url=f"https://www.google.com/search?q={quote_plus(item['name'])}",
        )
        self.add_item(google_button)

    async def on_timeout(self):
        await self.message.delete()

    @discord.ui.button(label="Icon", style=discord.ButtonStyle.gray)
    async def art(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if self.item["images"] is not None:
            if (
                self.item["images"][0]["height"] is None
                or self.item["images"][0]["width"] is None
            ):
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['images'][0]['width']}x{self.item['images'][0]['height']})"

            embed = discord.Embed(
                title=f"{self.item['name']} - Icon",
                description=description,
                color=Color.from_rgb(
                    r=self.colours[0], g=self.colours[1], b=self.colours[2]
                ),
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
            embed = discord.Embed(title="No icon available.", color=Color.red())
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )
            await interaction.edit_original_response(embed=embed)

        self.stop()


# Artist element function
async def artist(
    self,
    item: dict,
    top_tracks: dict,
    interaction: discord.Interaction,
    ephemeral: bool = False,
    responded: bool = False,
):
    """
    Handle Spotify artist embeds.
    """

    embed = discord.Embed(title=f"{item['name']}")

    embed.add_field(name="Followers", value=f"{item['followers']['total']:,}")
    embed.set_thumbnail(url=item["images"][0]["url"])

    embed.set_footer(
        text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
    )

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
        op_id=interaction.user.id,
    )

    if responded:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)


# --- Album Classes and Functions ---


class AlbumViewPages(View):
    def __init__(
        self,
        item: dict,
        artists: str,
        artist_img: str,
        cached: bool,
        pages: list,
        colours: list,
        op_id: int,
        add_button_url: str = None,
        add_button_text: str = None,
    ):
        super().__init__(timeout=259200)  # 3 days

        self.item = item
        self.artists = artists
        self.artist_img = artist_img
        self.cached = cached
        self.pages = pages
        self.colours = colours
        self.op_id = op_id
        self.add_button_url = add_button_url
        self.add_button_text = add_button_text

        self.page = 0
        self.locked = False

        if len(self.pages) > 1:
            # Hide first and prev buttons when starting
            for child in self.children:
                if child.custom_id == "first" or child.custom_id == "prev":
                    child.disabled = True
        else:
            for child in self.children:
                if (
                    child.custom_id == "first"
                    or child.custom_id == "prev"
                    or child.custom_id == "lock"
                    or child.custom_id == "next"
                    or child.custom_id == "last"
                ):
                    self.remove_item(child)

        # Add Open in Spotify button
        spotify_button = discord.ui.Button(
            label="Play on Spotify",
            style=discord.ButtonStyle.url,
            url=item["external_urls"]["spotify"],
            row=1,
        )
        self.add_item(spotify_button)

    # Page lock
    async def interaction_check(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id != self.op_id:
            if self.locked:
                embed = discord.Embed(
                    title="Locked",
                    description="The page is locked. Only the owner can control it.",
                    color=Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                return True
        else:
            return True

    # First page
    @discord.ui.button(emoji="⏮️", style=ButtonStyle.red, custom_id="first", row=0)
    async def first_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = 0

        for child in self.children:
            child.disabled = False

            if child.custom_id == "first" or child.custom_id == "prev":
                child.disabled = True

        # Create embed
        embed = discord.Embed(
            title=self.item["name"],
            description=self.pages[self.page],
            color=Color.from_rgb(self.colours[0], self.colours[1], self.colours[2]),
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}{' • Cached Link' if self.cached else ''}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.set_author(
            name=self.artists,
            url=self.item["artists"][0]["external_urls"]["spotify"],
            icon_url=self.artist_img,
        )

        embed.set_thumbnail(url=self.item["images"][0]["url"])

        await interaction.edit_original_response(embed=embed, view=self)

    # Previous page
    @discord.ui.button(emoji="⏪", style=ButtonStyle.gray, custom_id="prev", row=0)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.page - 1 == 0:
            self.page -= 1

            for child in self.children:
                child.disabled = False

                if child.custom_id == "first" or child.custom_id == "prev":
                    child.disabled = True
        else:
            self.page -= 1

            for child in self.children:
                child.disabled = False

        # Create embed
        embed = discord.Embed(
            title=self.item["name"],
            description=self.pages[self.page],
            color=Color.from_rgb(self.colours[0], self.colours[1], self.colours[2]),
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}{' • Cached Link' if self.cached else ''}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.set_author(
            name=self.artists,
            url=self.item["artists"][0]["external_urls"]["spotify"],
            icon_url=self.artist_img,
        )

        embed.set_thumbnail(url=self.item["images"][0]["url"])

        await interaction.edit_original_response(embed=embed, view=self)

    # Lock / unlock toggle
    @discord.ui.button(emoji="🔓", style=ButtonStyle.green, custom_id="lock", row=0)
    async def lock_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
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
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # Next page
    @discord.ui.button(emoji="⏩", style=ButtonStyle.gray, custom_id="next", row=0)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if (self.page + 1) == (len(self.pages) - 1):
            self.page += 1

            for child in self.children:
                child.disabled = False

                if child.custom_id == "next" or child.custom_id == "last":
                    child.disabled = True
        else:
            self.page += 1

            for child in self.children:
                child.disabled = False

        # Create embed
        embed = discord.Embed(
            title=self.item["name"],
            description=self.pages[self.page],
            color=Color.from_rgb(self.colours[0], self.colours[1], self.colours[2]),
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}{' • Cached Link' if self.cached else ''}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.set_author(
            name=self.artists,
            url=self.item["artists"][0]["external_urls"]["spotify"],
            icon_url=self.artist_img,
        )

        embed.set_thumbnail(url=self.item["images"][0]["url"])

        await interaction.edit_original_response(embed=embed, view=self)

    # Last page button
    @discord.ui.button(emoji="⏭️", style=ButtonStyle.green, custom_id="last", row=0)
    async def last_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.page = len(self.pages) - 1

        for child in self.children:
            child.disabled = False

            if child.custom_id == "next" or child.custom_id == "last":
                child.disabled = True

        # Create embed
        embed = discord.Embed(
            title=self.item["name"],
            description=self.pages[self.page],
            color=Color.from_rgb(self.colours[0], self.colours[1], self.colours[2]),
        )

        embed.set_footer(
            text=f"Controlling: @{interaction.user.name} - Page {self.page + 1}/{len(self.pages)}{' • Cached Link' if self.cached else ''}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.set_author(
            name=self.artists,
            url=self.item["artists"][0]["external_urls"]["spotify"],
            icon_url=self.artist_img,
        )

        embed.set_thumbnail(url=self.item["images"][0]["url"])

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Menu", style=discord.ButtonStyle.gray, row=1)
    async def menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AlbumMenuView(
            item=self.item,
            artists=self.artists,
            artist_img=self.artist_img,
            colours=self.colours,
            add_button_url=self.add_button_url,
            add_button_text=self.add_button_text,
        )

        view.message = await interaction.followup.send(
            view=view, ephemeral=True, wait=True
        )


class AlbumMenuView(View):
    def __init__(
        self,
        item: dict,
        artists: str,
        artist_img: str,
        colours: list,
        add_button_url: str = None,
        add_button_text: str = None,
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
            if (
                self.item["images"][0]["height"] is None
                or self.item["images"][0]["width"] is None
            ):
                description = "Viewing highest quality (Resolution unknown)"
            else:
                description = f"Viewing highest quality ({self.item['images'][0]['width']}x{self.item['images'][0]['height']})"

            embed = discord.Embed(
                title=f"{self.item['name']} - Album Art",
                description=description,
                color=Color.from_rgb(
                    r=self.colours[0], g=self.colours[1], b=self.colours[2]
                ),
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


# Album element function
async def album(
    self,
    item: dict,
    interaction: discord.Interaction,
    add_button_url: str = None,
    add_button_text: str = None,
    cached: bool = False,
    ephemeral: bool = False,
    responded: bool = False,
):
    """
    Handle Spotify album embeds.
    """

    artist_img = self.sp.artist(item["artists"][0]["external_urls"]["spotify"])[
        "images"
    ][0]["url"]

    pages = []
    page = [f"*Released **{item['release_date']}***\n"]

    # Generate artist list
    artists_list = []
    for artist in item["artists"]:
        artists_list.append(escape_markdown(artist["name"]))

    artists = truncate(", ".join(artists_list), 256)

    # Generate pages with 15 items
    for i, track in enumerate(item["tracks"]["items"]):
        # Generate track artist list
        track_artists_list = []
        for artist in track["artists"]:
            track_artists_list.append(escape_markdown(artist["name"]))

        # Only show artists if they are not the same as the album artist
        if track_artists_list == artists_list:
            page.append(f"{i + 1}. **{truncate(track['name'], 200)}**")
        else:
            track_artists = truncate(", ".join(track_artists_list))

            page.append(
                f"{i + 1}. **{truncate(escape_markdown(item['tracks']['items'][i]['name']))}** - {track_artists}"
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

    # Create embed
    embed = discord.Embed(
        title=item["name"],
        description=pages[0],
        color=Color.from_rgb(r=colours[0], g=colours[1], b=colours[2]),
    )

    embed.set_footer(
        text=f"{'Controlling: ' if len(pages) > 1 else ''}@{interaction.user.name} - Page 1/{len(pages)}{' • Cached Link' if cached else ''}",
        icon_url=interaction.user.display_avatar.url,
    )

    embed.set_author(
        name=artists,
        url=item["artists"][0]["external_urls"]["spotify"],
        icon_url=artist_img,
    )

    embed.set_thumbnail(url=item["images"][0]["url"])

    view = AlbumViewPages(
        item=item,
        artists=artists,
        artist_img=artist_img,
        cached=cached,
        pages=pages,
        colours=colours,
        op_id=interaction.user.id,
        add_button_url=add_button_url,
        add_button_text=add_button_text,
    )

    if responded:
        await interaction.edit_original_response(embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
