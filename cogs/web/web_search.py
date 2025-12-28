import os
import urllib.parse
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View

from lib.helpers.global_alias import add_global_aliases, global_alias
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class WebSearchCommandsCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        add_global_aliases(self, bot)

    def _create_urban_embed(self, data: dict) -> list[discord.Embed]:
        embed = discord.Embed(
            title=f"{data['word']}",
            description=f"**Author: {data['author']}**\n\n||{(data['definition'].replace('[', '')).replace(']', '')}||",
            url=data["permalink"],
            color=Color.random(),
        )
        embed.set_author(
            name="Urban Dictionary",
            icon_url="https://media.licdn.com/dms/image/v2/D560BAQGlykJwWd7v-g/company-logo_200_200/company-logo_200_200/0/1718946315384/urbandictionary_logo?e=2147483647&v=beta&t=jnPuu32SKBWZsFOfOHz7KugJq0S2UARN8CL0wOAyyro",
        )

        return [
            discord.Embed(
                title=f"{self.bot.warn_emoji} Content Warning",
                description="Urban Dictionary has very little moderation and content may be inappropriate! View at your own risk.",
                color=Color.orange(),
            ),
            embed,
        ]

    @commands.hybrid_group(name="search", description="Search the web using various services.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def search_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    # Urban Dictionary command
    @search_group.command(
        name="urban-dictionary",
        description="Search Urban Dictionary. Warning: content is mostly unmoderated and may be inappropriate!",
        aliases=["ud", "urbandictionary"],
    )
    @global_alias("urban-dictionary")
    @global_alias("ud")
    @global_alias("urbandictionary")
    @app_commands.describe(page="Optional: page to jump to. Defaults to first page.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 10)
    async def urban_dict(
        self,
        ctx: commands.Context["TitaniumBot"],
        *,
        query: str,
        page: app_commands.Range[int, 1, 10] = 1,
        ephemeral: bool = False,
    ):
        await ctx.defer(ephemeral=ephemeral)

        item_list: list[dict] = []
        embeds_list: list[list[discord.Embed]] = []

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.urbandictionary.com/v0/define?term={urllib.parse.quote(query)}"
            ) as request:
                request_data = await request.json()

        if len(request_data["list"]) != 0:
            page = max(1, min(len(request_data["list"]), page))
            item_list = request_data["list"]

            try:
                for item in item_list:
                    embeds_list.append(self._create_urban_embed(item))
            except IndexError:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description=f"**Page {page}** does not exist. Try another search query.",
                    color=Color.red(),
                )
                embed.set_footer(
                    text=f"@{ctx.author.name} • Page 1/{len(item_list)}",
                    icon_url=ctx.author.display_avatar.url,
                )

                await ctx.reply(embed=embed, ephemeral=ephemeral)
                return

            embeds_list[0][1].set_footer(
                text=f"Controlling: @{ctx.author.name}"
                if len(item_list) > 1
                else f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            if len(item_list) == 1:
                await ctx.reply(embeds=embeds_list[0], ephemeral=ephemeral)
            else:
                await ctx.reply(
                    embeds=embeds_list[0],
                    view=PaginationView(embeds=embeds_list, timeout=900, page_offset=page),
                    ephemeral=ephemeral,
                )
        else:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{query}`. Please try a different search term.",
                color=Color.red(),
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)

    # Wikipedia command
    @search_group.command(
        name="wikipedia", description="Search Wikipedia for information.", aliases=["wiki"]
    )
    @global_alias("wikipedia")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false."
    )
    @commands.cooldown(1, 5)
    async def wiki(
        self, ctx: commands.Context["TitaniumBot"], *, search: str, ephemeral: bool = False
    ):
        await ctx.defer(ephemeral=ephemeral)

        headers = {"User-Agent": os.getenv("WIKIPEDIA_API_USER_AGENT", "")}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.wikimedia.org/core/v1/wikipedia/en/search/title?q={urllib.parse.quote(search)}&limit=1",
                headers=headers,
            ) as request:
                if request.status != 200:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} No Results Found",
                        description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                        color=Color.red(),
                    )
                    embed.set_author(
                        name="Wikipedia",
                        icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    await ctx.reply(embed=embed, ephemeral=ephemeral)
                    return

                page_data = await request.json()

        if not page_data.get("pages") or len(page_data["pages"]) == 0:
            embed = discord.Embed(
                title=f"{self.bot.error_emoji} No Results Found",
                description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                color=Color.red(),
            )
            embed.set_author(
                name="Wikipedia",
                icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
            )
            embed.set_footer(
                text=f"@{ctx.author.name}",
                icon_url=ctx.author.display_avatar.url,
            )

            await ctx.reply(embed=embed, ephemeral=ephemeral)
            return

        target_page = page_data["pages"][0]

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{target_page['key']}",
                headers=headers,
            ) as request:
                if request.status != 200:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} No Results Found",
                        description=f"Couldn't find any results for `{search}`. Please try a different search term.",
                        color=Color.red(),
                    )
                    embed.set_author(
                        name="Wikipedia",
                        icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
                    )
                    embed.set_footer(
                        text=f"@{ctx.author.name}",
                        icon_url=ctx.author.display_avatar.url,
                    )

                    await ctx.reply(embed=embed, ephemeral=ephemeral)
                    return

                page = await request.json()

        embed = discord.Embed(
            title=page["title"],
            description=page["extract"],
            color=Color.from_rgb(r=255, g=255, b=255),
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.set_author(
            name="Wikipedia",
            icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
        )

        view = View()
        view.add_item(
            discord.ui.Button(
                label="Read More",
                style=discord.ButtonStyle.url,
                url=page["content_urls"]["desktop"]["page"],
            )
        )

        await ctx.reply(embed=embed, view=view, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(WebSearchCommandsCog(bot))
