import html
import os
import re
import urllib.parse
from datetime import datetime
from textwrap import shorten
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

import aiohttp
import discord
import pycountry
from discord import Colour, MediaGalleryItem, app_commands
from discord.ext import commands
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
    View,
)
from pycountry.db import Country

from lib.helpers.country import fuzzy_search_country
from lib.views.pagination import PaginationV2View

if TYPE_CHECKING:
    from main import TitaniumBot

ESRB_RATINGS = {
    "e": "Everyone",
    "e10+": "Everyone 10+",
    "t": "Teen",
    "m": "Mature",
    "ao": "Adults Only",
    "ec": "Early Childhood",
    "rp": "Rating Pending",
    "nr": "Not Rated",
}


class UrbanDictionaryDef(TypedDict):
    author: str
    current_vote: str
    defid: int
    definition: str
    example: str
    permalink: str
    thumbs_down: int
    thumbs_up: int
    word: str
    written_on: str
    udimg_url: str


class ReleaseDate(TypedDict):
    coming_soon: bool
    date: str


class AgeRating(TypedDict):
    rating: str
    descriptors: str
    use_age_gate: Literal["true", "0"]
    required_age: str


class PriceData(TypedDict):
    currency: str
    initial: int
    final: int
    discount_percent: int
    initial_formatted: str
    final_formatted: str


class SteamResult(TypedDict):
    type: str
    name: str
    id: int
    tiny_image: str
    platforms: dict[Literal["windows", "mac", "linux"], bool]
    streamingvideo: bool
    price: NotRequired[dict[Literal["initial", "final"], int]]


class SteamGame(SteamResult):
    short_description: str
    header_image: str
    capsule_image: str
    capsule_imagev5: str
    background_raw: str
    website: str
    release_date: ReleaseDate
    developers: list[str]
    publishers: list[str]
    dlc: NotRequired[list]
    price_overview: NotRequired[PriceData]
    is_free: bool
    recommendations: NotRequired[dict[Literal["total"], int]]
    achievements: NotRequired[dict[Literal["total"], int]]
    ratings: (
        dict[
            Literal[
                "esrb", "pegi", "usk", "gmedia", "dejus", "steam_germany", "igrs", "steam_australia"
            ],
            AgeRating,
        ]
        | None
    )


class SteamSearchResults(TypedDict):
    total: int
    items: list[SteamResult]


class SteamGameButton(Button):
    def __init__(
        self, result: SteamResult, country: str, info_emoji: discord.Emoji | str, ephemeral: bool
    ) -> None:
        super().__init__(label="View Info", emoji=info_emoji)
        self.result = result
        self.country = country
        self.ephemeral = ephemeral

    async def callback(self, interaction: discord.Interaction["TitaniumBot"]) -> Any:
        await interaction.response.defer(ephemeral=self.ephemeral)

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://store.steampowered.com/api/appdetails?appids={self.result['id']}&cc={self.country}&l=english"
            ) as request,
        ):
            request.raise_for_status()
            request_data: dict = await request.json()

            if (
                (
                    self.result["id"] in request_data
                    and request_data[self.result["id"]]["success"] == False
                )
                or next(iter(request_data), None) is None
                or request_data[next(iter(request_data))]["success"] == False
            ):
                raise RuntimeError(f"Steam failed to get data for id {self.result['id']}")

            game: SteamGame = request_data[next(iter(request_data))]["data"]

        view = LayoutView()
        container = Container(
            accent_colour=Colour.light_grey(),
        )

        if game["capsule_image"]:
            container.add_item(
                Section(
                    TextDisplay(
                        f"## {' '.join(game['name'].splitlines())}\n-# by {', '.join(game['developers'])}\n\n{html.unescape(game['short_description'])}"
                    ),
                    accessory=Thumbnail(media=game["capsule_image"]),
                )
            )
        else:
            container.add_item(
                TextDisplay(
                    f"## {' '.join(game['name'].splitlines())}\n{game['short_description']}"
                )
            )

        if game["background_raw"]:
            container.add_item(MediaGallery(MediaGalleryItem(game["header_image"])))

        container.add_item(Separator(spacing=discord.SeparatorSpacing.small))

        price = game.get("price_overview")

        if price:
            price_str = f"💵 {f'~~{price["initial_formatted"]}~~ ' if price['initial_formatted'] else ''}**{price['final_formatted']}**{f' ({price["discount_percent"]}% off)' if price['discount_percent'] else ''} - "
        elif game["is_free"]:
            price_str = "💵 **Free** - "
        else:
            price_str = ""

        container.add_item(
            TextDisplay(
                f"{price_str}{game['release_date']['date']} - {len(game.get('dlc', [])) or 'No'} addon{'s' if len(game.get('dlc', [])) != 1 else ''}"
            )
        )

        container.add_item(Separator(spacing=discord.SeparatorSpacing.small))

        age_ratings = []
        ratings = game["ratings"]

        if isinstance(ratings, dict):
            if "pegi" in ratings:
                age_ratings.append(f"🔞 PEGI: `{ratings['pegi']['rating']}`")
            if "esrb" in ratings:
                rating = ESRB_RATINGS.get(
                    ratings["esrb"]["rating"].lower(),
                    ratings["esrb"]["rating"].upper(),
                )
                age_ratings.append(f"🔞 ESRB: `{rating}`")

        recommendations = game.get("recommendations")
        achievements = game.get("achievements")
        total = str(achievements["total"]) if achievements else "No"
        container.add_item(
            TextDisplay(
                f"🏆 {total} achievements - 👍 {(recommendations['total'] if recommendations else 0):,} - {' - '.join(age_ratings) if age_ratings else '🔞 No available age ratings'}"
            )
        )

        container.add_item(Separator(spacing=discord.SeparatorSpacing.small))

        row = ActionRow(
            Button(
                label="Store Page", url=f"https://store.steampowered.com/app/{self.result['id']}/"
            ),
            Button(
                label="Steam Community", url=f"https://steamcommunity.com/app/{self.result['id']}/"
            ),
        )
        if game["website"]:
            row.add_item(Button(label="Game Website", url=game["website"]))

        container.add_item(row)
        view.add_item(container)

        await interaction.edit_original_response(view=view)


class SteamResultsContainer(Container):
    def __init__(
        self,
        query: str,
        country: Country,
        page: list[SteamResult],
        total: int,
        info_emoji: discord.Emoji | str,
        ephemeral: bool,
    ) -> None:
        super().__init__(accent_colour=Colour.light_grey())

        self.add_item(
            TextDisplay(
                f"### Steam Search\n## [{' '.join(query.splitlines())}](https://store.steampowered.com/search?term={urllib.parse.quote(query)})\n"
                f"Found **{total}** results on Steam."
            )
        )
        self.add_item(Separator(spacing=discord.SeparatorSpacing.large))

        for i, game in enumerate(page):
            if i != 0:
                self.add_item(Separator())

            price = game.get("price")
            self.add_item(
                Section(
                    TextDisplay(
                        f"### [{' '.join(game['name'].splitlines())}](https://store.steampowered.com/app/{game['id']}/)\n`{f'{price["final"] / 100:.2f}' if price else 'Free / Unknown'}`"
                    ),
                    accessory=SteamGameButton(game, country.alpha_2, info_emoji, ephemeral),
                )
            )

        self.add_item(Separator(spacing=discord.SeparatorSpacing.large))
        self.add_item(
            TextDisplay(
                f"-# {country.flag} Showing results and prices for games in **{country.name}**. Select a different country using the `country` argument."
            )
        )


class UrbanDictionaryContainer(Container):
    def __init__(self, data: UrbanDictionaryDef) -> None:
        super().__init__(accent_colour=Colour.from_str("#F1FE5F"))

        definition = re.sub(
            r"\[([^\[\]]+)\](?!\()",
            lambda match: (
                f"[{match.group(1)}](https://www.urbandictionary.com/define.php?term={urllib.parse.quote(match.group(1))})"
            ),
            data["definition"],
        )
        self.add_item(
            Section(
                TextDisplay(
                    f"## [{' '.join(data['word'].splitlines())}]({data['permalink']})\n-# by {data['author']}\n\n{definition}"
                ),
                accessory=Thumbnail(media="https://titanium.fyi/assets/ud.png"),
            )
        )

        self.add_item(Separator(spacing=discord.SeparatorSpacing.small))

        example = re.sub(
            r"\[([^\[\]]+)\](?!\()",
            lambda match: (
                f"[{match.group(1)}](https://www.urbandictionary.com/define.php?term={urllib.parse.quote(match.group(1))})"
            ),
            data["example"],
        )
        self.add_item(TextDisplay(f"### Example\n{example}"))

        self.add_item(Separator(spacing=discord.SeparatorSpacing.small))
        self.add_item(
            TextDisplay(
                f"Written {discord.utils.format_dt(datetime.fromisoformat(data['written_on']))}"
            )
        )


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class WebSearchCommandsCog(
    commands.GroupCog, group_name="search", description="Search the web using various services."
):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    # Urban Dictionary command
    @app_commands.command(
        name="urban-dictionary",
        description="Search Urban Dictionary for word and phrase definitions.",
        nsfw=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        query="The term to search for.",
        page="Optional: page to jump to. Defaults to first page.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def urban_dict(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        query: str,
        page: app_commands.Range[int, 1, 10] = 1,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://api.urbandictionary.com/v0/define?term={urllib.parse.quote(query)}"
            ) as request,
        ):
            request_data: dict = await request.json()

        items: list[UrbanDictionaryDef] = request_data.get("list", [])
        if not items:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{query}`. Please try a different search term.",
                colour=Colour.red(),
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

        pages = [UrbanDictionaryContainer(data=item) for item in items]
        view = PaginationV2View(pages=pages)

        await interaction.followup.send(view=view, ephemeral=ephemeral)

    # Wikipedia command
    @app_commands.command(name="wikipedia", description="Search Wikipedia for information.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        search="The term to search for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def wiki(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        search: str,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        headers = {"User-Agent": os.getenv("REQUEST_USER_AGENT", "")}

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://api.wikimedia.org/core/v1/wikipedia/en/search/title?q={urllib.parse.quote(search)}&limit=1",
                headers=headers,
            ) as request,
        ):
            if request.status == 404:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Results Found",
                    description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                    colour=Colour.red(),
                )
                embed.set_author(
                    name="Wikipedia",
                    icon_url="https://titanium.fyi/assets/wikipedia.png",
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            request.raise_for_status()
            page_data: dict = await request.json()

        if not page_data.get("pages") or len(page_data["pages"]) == 0:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                colour=Colour.red(),
            )
            embed.set_author(
                name="Wikipedia",
                icon_url="https://titanium.fyi/assets/wikipedia.png",
            )
            embed.set_footer(
                text=f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        target_page = page_data["pages"][0]

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{target_page['key']}",
                headers=headers,
            ) as request,
        ):
            if request.status == 404:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} No Results Found",
                    description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                    colour=Colour.red(),
                )
                embed.set_author(
                    name="Wikipedia",
                    icon_url="https://titanium.fyi/assets/wikipedia.png",
                )
                embed.set_footer(
                    text=f"@{interaction.user.name}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            request.raise_for_status()
            page = await request.json()

        embed = discord.Embed(
            title=page["title"],
            description=page["extract"],
            colour=Colour.from_rgb(r=255, g=255, b=255),
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_author(
            name="Wikipedia",
            icon_url="https://titanium.fyi/assets/wikipedia.png",
        )

        view = View()
        view.add_item(
            Button(
                label="Read More",
                style=discord.ButtonStyle.url,
                url=page["content_urls"]["desktop"]["page"],
            )
        )

        await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)

    async def country_autocomplete(
        self, interaction: discord.Interaction["TitaniumBot"], current: str
    ) -> list[app_commands.Choice[str]]:
        countries: list[app_commands.Choice[str]] = []

        if not current.strip():
            countries.append(
                app_commands.Choice(name="Start typing to search for a country", value="")
            )
            countries.extend(
                [
                    app_commands.Choice(
                        name=shorten(f"{c.flag} {c.name}", width=25, placeholder="..."),
                        value=c.alpha_2,
                    )
                    for c in list(pycountry.countries)[:24]
                ]
            )
        else:
            countries_raw = await fuzzy_search_country(current)
            for c in countries_raw[:25]:
                countries.append(
                    app_commands.Choice(
                        name=shorten(f"{c.flag} {c.name}", width=25, placeholder="..."),
                        value=c.alpha_2,
                    )
                )

        return countries

    # Steam command
    @app_commands.command(
        name="steam",
        description="Search the Steam Store for games and software.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        query="The term to search for.",
        country="Optional: the country to search in. Defaults to United Kingdom.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.autocomplete(country=country_autocomplete)
    @app_commands.checks.cooldown(1, 5)
    async def steam(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        query: str,
        country: str = "GB",
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        resolved_country: Country | None = None
        if len(country) == 2:
            resolved_country = pycountry.countries.get(alpha_2=country)

        if not resolved_country:
            countries_raw = await fuzzy_search_country(country, cutoff=70)
            if len(countries_raw) > 0:
                resolved_country = countries_raw[0]

        if not resolved_country:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} Country Not Found",
                description=f"Couldn't find a country called `{country}`. Please select a country from the list or enter a valid country name or 2 character code.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(query)}&l=english&cc={resolved_country.alpha_2}"
            ) as request,
        ):
            request.raise_for_status()
            search_results: SteamSearchResults = await request.json()

        results = list(filter(lambda x: x["type"] == "app", search_results["items"]))
        if search_results["total"] == 0 or not results:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{query}`. Please check the game is available in your selected country, and try again.",
                colour=Colour.red(),
            )
            embed.set_footer(
                text=f"{resolved_country.flag} Showing results and prices for games in {resolved_country.name}. Select a different country using the country argument."
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        pages: list[SteamResultsContainer] = []
        chunks = discord.utils.as_chunks(results, 5)
        for chunk in chunks:
            pages.append(
                SteamResultsContainer(
                    query=query,
                    country=resolved_country,
                    page=chunk,
                    total=search_results["total"],
                    info_emoji=self.bot.info_emoji,
                    ephemeral=ephemeral,
                )
            )

        view = PaginationV2View(pages=pages)
        await interaction.followup.send(view=view, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(WebSearchCommandsCog(bot))
