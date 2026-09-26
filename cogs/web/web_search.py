import os
import urllib.parse
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

import aiohttp
import discord
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

from lib.views.pagination import PaginationV2View, PaginationView

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
    ratings: dict[
        Literal[
            "esrb", "pegi", "usk", "gmedia", "dejus", "steam_germany", "igrs", "steam_australia"
        ],
        AgeRating,
    ]


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
                        f"## {' '.join(game['name'].splitlines())}\n-# By {', '.join(game['developers'])}\n\n{game['short_description']}"
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
            price_str = f"{f'~~{price["initial_formatted"]}~~ ' if price['initial_formatted'] else ''}**{price['final_formatted']}**{f' ({price["discount_percent"]}% off)' if price['discount_percent'] else ''}"
        elif game["is_free"]:
            price_str = "Free"
        else:
            price_str = "Unavailable"

        container.add_item(
            TextDisplay(
                f"💵 {price_str} - {game['release_date']['date']} - {len(game.get('dlc', [])) or 'No'} addons"
            )
        )

        container.add_item(Separator(spacing=discord.SeparatorSpacing.small))

        age_ratings = []
        if "pegi" in game["ratings"]:
            age_ratings.append(f"🔞 PEGI: `{game['ratings']['pegi']['rating']}`")
        if "esrb" in game["ratings"]:
            rating = ESRB_RATINGS.get(
                game["ratings"]["esrb"]["rating"].lower(), game["ratings"]["esrb"]["rating"].upper()
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
        country: str,
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
                        f"### [{' '.join(game['name'].splitlines())}](https://store.steampowered.com/app/{game['id']}/)\n{f'£{price["final"] / 100:.2f}' if price else '£0.00'}"
                    ),
                    accessory=SteamGameButton(game, country, info_emoji, ephemeral),
                )
            )


# TODO: commands here apart from steam were ripped from v1 with little changes, could do with a rewrite
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class WebSearchCommandsCog(
    commands.GroupCog, group_name="search", description="Search the web using various services."
):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    def _create_urban_embed(self, data: dict) -> list[discord.Embed]:
        embed = discord.Embed(
            title=f"{data['word']}",
            description=f"**Author: {data['author']}**\n\n||{(data['definition'].replace('[', '')).replace(']', '')}||",
            url=data["permalink"],
            colour=Colour.from_str("#F1FE5F"),
        )
        embed.set_author(
            name="Urban Dictionary",
            icon_url="https://titanium.fyi/assets/ud.png",
        )

        return [
            discord.Embed(
                title=f"{self.bot.warn_emoji} Content Warning",
                description="Urban Dictionary has very little moderation and content may be inappropriate! View at your own risk.",
                colour=Colour.orange(),
            ),
            embed,
        ]

    # Urban Dictionary command
    @app_commands.command(
        name="urban-dictionary",
        description="Search Urban Dictionary. Warning: content is mostly unmoderated and may be inappropriate!",
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

        item_list: list[dict] = []
        embeds_list: list[list[discord.Embed]] = []

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://api.urbandictionary.com/v0/define?term={urllib.parse.quote(query)}"
            ) as request,
        ):
            request_data = await request.json()

        if len(request_data["list"]) != 0:
            page = max(1, min(len(request_data["list"]), page))
            item_list = request_data["list"]

            try:
                for item in item_list:
                    embeds_list.append(self._create_urban_embed(item))
            except IndexError:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Not Found",
                    description=f"**Page {page}** does not exist. Please try a different search term.",
                    colour=Colour.red(),
                )
                embed.set_footer(
                    text=f"@{interaction.user.name} • Page 1/{len(item_list)}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                return

            embeds_list[0][1].set_footer(
                text=f"Controlling: @{interaction.user.name}"
                if len(item_list) > 1
                else f"@{interaction.user.name}",
                icon_url=interaction.user.display_avatar.url,
            )

            if len(item_list) == 1:
                await interaction.followup.send(embeds=embeds_list[0], ephemeral=ephemeral)
            else:
                await interaction.followup.send(
                    embeds=embeds_list[0],
                    view=PaginationView(embeds=embeds_list, timeout=900, page_offset=page),
                    ephemeral=ephemeral,
                )
        else:
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
            page_data = await request.json()

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

    # Steam command
    @app_commands.command(
        name="steam",
        description="Search the Steam Store for games and software.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        query="The term to search for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def steam(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        query: str,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"https://store.steampowered.com/api/storesearch/?term={urllib.parse.quote(query)}&l=english&cc=gb"
            ) as request,
        ):
            request.raise_for_status()
            search_results: SteamSearchResults = await request.json()

        results = list(filter(lambda x: x["type"] == "app", search_results["items"]))
        if search_results["total"] == 0 or not results:
            embed = discord.Embed(
                title=f"{interaction.client.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{query}`. Please check your query and try again.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        pages: list[SteamResultsContainer] = []
        chunks = discord.utils.as_chunks(results, 5)
        for chunk in chunks:
            pages.append(
                SteamResultsContainer(
                    query=query,
                    country="gb",
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
