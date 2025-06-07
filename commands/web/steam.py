import html
from textwrap import shorten
from urllib.parse import quote

import aiohttp
import discord
import discord.ext
from discord import app_commands
from discord.ext import commands
from discord.ui import View


class SteamCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    steamGroup = app_commands.Group(
        name="steam",
        description="Steam related commands.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Steam Game command
    @steamGroup.command(name="game", description="Get info about a Steam game.")
    @app_commands.describe(
        game="The name of the game to search for.",
        currency="The currency to display the price in.",
        ephemeral="Whether to send the response as ephemeral (only visible to you).",
    )
    @app_commands.choices(
        currency=[
            app_commands.Choice(
                name="British Pounds",
                value="GB",
            ),
            app_commands.Choice(
                name="Euro",
                value="BG",
            ),
            app_commands.Choice(
                name="United States Dollar",
                value="US",
            ),
            app_commands.Choice(
                name="Australian Dollar",
                value="AU",
            ),
            app_commands.Choice(
                name="Canadian Dollar",
                value="CA",
            ),
            app_commands.Choice(
                name="New Zealand Dollar",
                value="NZ",
            ),
            app_commands.Choice(
                name="Indian Rupee",
                value="IN",
            ),
            app_commands.Choice(
                name="Russian Ruble",
                value="RU",
            ),
            app_commands.Choice(
                name="Ukrainian Hryvnia",
                value="UA",
            ),
        ],
    )
    async def steam_game(
        self,
        interaction: discord.Interaction,
        game: str,
        currency: app_commands.Choice[str],
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        url = f"https://store.steampowered.com/api/storesearch/?term={quote(game)}&l=english&cc={currency.value}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                jr = await response.json()
                total_items = int(jr["total"])
                if total_items == 0:
                    embed = discord.Embed(
                        title="No Results Found",
                        description=f'No results found for "{game}". Please try a different search term.',
                        color=discord.Color.red(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name}",
                        icon_url=interaction.user.display_avatar.url,
                    )
                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
                    return
                else:
                    all_items = jr["items"]

        embed = discord.Embed(
            title="Select Game",
            description=f'Found {total_items} results, showing results for "{game}".\n\nCan\u0027t find what you\u0027re looking for? Try to be more specific with your query.',
            color=0x0087CC,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        # Add each game's option
        options = []
        id_list = []

        for i in range(min(5, len(all_items))):
            name = shorten(all_items[i]["name"], width=100, placeholder="…")
            appid = all_items[i]["id"]
            price_info = all_items[i].get("price")

            if price_info and "initial" in price_info and "currency" in price_info:
                price_value = price_info["initial"] / 100
                price = f"{int(price_value) if price_value.is_integer() else f'{price_value:.2f}'} {price_info['currency']}"
            else:
                price = "Free"

            try:
                score = int(all_items[i]["metascore"])
            except (KeyError, ValueError, TypeError):
                score = 0

            description_items = [
                price,
                f"{score} MS" if score > 0 else None,
                f"ID {appid}",
            ]
            desctext = " | ".join(filter(None, description_items))
            desctext = shorten(desctext, width=100, placeholder="…")

            options.append(
                discord.SelectOption(
                    label=name,
                    description=desctext,
                    value=str(appid),
                )
            )

            id_list.append(appid)

        class GameSelectView(View):
            def __init__(self, options: list):
                super().__init__(timeout=120)  # 2 minute timeout

                self.msg_id: int = None

                dropdown_instance = Dropdown(options)
                self.add_item(dropdown_instance)

                # Pass in view's self to allow it to be stopped
                dropdown_instance.viewSelf = self

            async def on_timeout(self) -> None:
                try:
                    for item in self.children:
                        item.disabled = True

                    msg = await interaction.channel.fetch_message(self.msg_id)
                    await msg.edit(view=self)
                except Exception:
                    pass

        # Game select dropdown class
        class Dropdown(discord.ui.Select):
            def __init__(self, options: list):
                super().__init__(
                    placeholder="Select Game",
                    min_values=1,
                    max_values=1,
                    options=options,
                )

                self.viewSelf: View = None

            # Callback
            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()

                self.viewSelf.stop()
                list_place = id_list.index(int(self.values[0]))

                id = all_items[list_place]["id"]
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://store.steampowered.com/api/appdetails?appids={id}&cc={currency.value}"
                    ) as response:
                        response.raise_for_status()
                        game_data = await response.json()
                        game_info = game_data[str(id)]["data"]

                price_info = game_info.get("price_overview")
                score = game_info.get("metacritic", {}).get("score", 0)
                score_emoji = (
                    ":green_circle:"
                    if score >= 75
                    else ":yellow_circle:"
                    if score >= 50
                    else ":red_circle:"
                )

                if game_info["is_free"]:
                    price = "Free"
                elif (
                    price_info and "initial" in price_info and "currency" in price_info
                ):
                    # check for discount
                    if price_info.get("discount_percent", 0) > 0:
                        initial = price_info["initial"] / 100
                        final = price_info["final"] / 100
                        price = f"~~{int(initial) if initial.is_integer() else f'{initial:.2f}'}~~ {int(final) if final.is_integer() else f'{final:.2f}'} {price_info['currency']}"
                    else:
                        initial = price_info["initial"] / 100
                        price = f"{int(initial) if initial.is_integer() else f'{initial:.2f}'} {price_info['currency']}"
                else:
                    price = "N/A"

                # game description
                desc = f"{html.unescape(game_info['short_description'])}\n\n**"

                # achievements
                desc += f"{game_info['achievements']['total'] if 'achievements' in game_info else 'No'} achievements\n"

                # release date
                # listed but release date unknown
                if (
                    game_info["release_date"]["coming_soon"]
                    and game_info["release_date"]["date"] == "Coming soon"
                ):
                    desc += "Coming soon\n"
                # release date known but not released yet
                elif (
                    game_info["release_date"]["coming_soon"]
                    and game_info["release_date"]["date"] != "Coming soon"
                ):
                    desc += f"Releasing: {game_info['release_date']['date']}\n"
                # fully released
                else:
                    desc += f"{'Released: '}{game_info['release_date']['date']}\n"

                # price
                desc += f"{price}\n"

                # metascore
                if score > 0:
                    desc += f"Metascore: {score_emoji} {score}\n"
                desc += "**"

                embed = discord.Embed(
                    title=game_info["name"],
                    description=desc,
                    color=discord.Color.random(),
                )
                embed.set_image(url=game_info.get("header_image", ""))

                steam_button = discord.ui.Button(
                    label="Steam",
                    style=discord.ButtonStyle.url,
                    url=f"https://store.steampowered.com/app/{game_info['steam_appid']}",
                )

                if game_info.get("website"):
                    website_button = discord.ui.Button(
                        label="Website",
                        style=discord.ButtonStyle.url,
                        url=game_info["website"],
                    )

                view = View()
                view.add_item(steam_button)
                if game_info.get("website"):
                    view.add_item(website_button)

                embed.set_footer(
                    text=f"@{interaction.user.name} • App ID: {game_info['steam_appid']}",
                    icon_url=interaction.user.display_avatar.url,
                )

                await interaction.edit_original_response(embed=embed, view=view)

        # Send the initial embed with the select menu
        view = GameSelectView(options)
        msg = await interaction.followup.send(
            embed=embed, view=view, ephemeral=ephemeral, wait=True
        )
        view.msg_id = msg.id


async def setup(bot):
    await bot.add_cog(SteamCommands(bot))
