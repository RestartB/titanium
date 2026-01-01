import os
from typing import TYPE_CHECKING, Optional

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands

from lib.helpers.global_alias import add_global_aliases, global_alias
from lib.views.pagination import PaginationView

if TYPE_CHECKING:
    from main import TitaniumBot


class ReviewsCommandsCog(commands.Cog):
    REQUEST_HEADERS = {
        "User-Agent": os.getenv("REQUEST_USER_AGENT", ""),
    }

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        add_global_aliases(self, bot)

    @commands.hybrid_group(name="reviews", description="Get reviews for a user.", fallback="user")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="Optional: the user to get reviews for. Defaults to yourself.")
    @commands.cooldown(1, 5)
    async def reviews_group(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: Optional[discord.User | discord.Member] | None,
    ) -> None:
        if user is None:
            user = ctx.author

        review_list = []

        # Send request to ReviewDB
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews?offset=0",
                headers=self.REQUEST_HEADERS,
            ) as request:
                review_response = await request.json()

        for review in review_response["reviews"][1:]:
            review_list.append(review)

        while True:
            if not review_response["success"]:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="ReviewDB has encountered an error. Titanium will not continue. Please try again later.",
                    color=Color.red(),
                )
                await ctx.reply(embed=embed)

                return
            else:
                if review_response["hasNextPage"]:
                    # Send request to ReviewDB
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://manti.vendicated.dev/api/reviewdb/users/{user.id}/reviews?offset={len(review_list)}",
                            headers=self.REQUEST_HEADERS,
                        ) as request:
                            review_response = await request.json()

                    for review in review_response["reviews"]:
                        review_list.append(review)
                else:
                    break

        review_amount = len(review_list)
        count_per_page = 4

        pages: list[discord.Embed] = []
        page = discord.Embed(
            title="ReviewDB User Reviews",
            description=f"There {'are' if review_amount > 1 else 'is'} **{review_amount} review{'s' if review_amount > 1 else ''}** for this user.",
            color=Color.random(),
        )
        page.set_author(
            name=f"@{user.name}",
            icon_url=user.display_avatar.url,
        )

        for i, review in enumerate(review_list, start=1):
            page.add_field(
                name=f"{i}. @{discord.utils.escape_markdown(review['sender']['username'])} - <t:{review['timestamp']}:d>",
                value=f"{review['comment'] if len(review['comment']) <= 1024 else review['comment'][:1021] + '...'}",
                inline=False,
            )

            if i % count_per_page == 0 or i == review_amount:
                pages.append(page)
                page = discord.Embed(
                    title="ReviewDB User Reviews",
                    description=f"There {'are' if review_amount > 1 else 'is'} **{review_amount} review{'s' if review_amount > 1 else ''}** for this user.",
                    color=Color.random(),
                )
                page.set_author(
                    name=f"@{user.name}",
                    icon_url=user.display_avatar.url,
                )

        pages[0].set_footer(
            text=f"Controlling: @{ctx.author.name}" if len(pages) > 1 else f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        if len(pages) > 1:
            view = PaginationView(embeds=pages, timeout=180)
            await ctx.reply(embed=pages[0], view=view)
        else:
            await ctx.reply(embed=pages[0])

    # Server reviews command
    @reviews_group.command(name="server", description="Get reviews for the server.")
    @global_alias("serverreviews")
    @global_alias("server_reviews")
    @commands.guild_only()
    @commands.cooldown(1, 5)
    async def server_reviews(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        if not ctx.guild:
            raise commands.NoPrivateMessage

        review_list = []

        # Send request to ReviewDB
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://manti.vendicated.dev/api/reviewdb/users/{ctx.guild.id}/reviews?offset=0",
                headers=self.REQUEST_HEADERS,
            ) as request:
                review_response = await request.json()

        for review in review_response["reviews"][1:]:
            review_list.append(review)

        while True:
            if not review_response["success"]:
                embed = discord.Embed(
                    title=f"{self.bot.error_emoji} Error",
                    description="ReviewDB has encountered an error. Titanium will not continue. Please try again later.",
                    color=Color.red(),
                )

                await ctx.reply(embed=embed)
                return
            else:
                if review_response["hasNextPage"]:
                    # Send request to ReviewDB
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"https://manti.vendicated.dev/api/reviewdb/users/{ctx.guild.id}/reviews?offset={len(review_list)}",
                            headers=self.REQUEST_HEADERS,
                        ) as request:
                            review_response = await request.json()

                    for review in review_response["reviews"]:
                        review_list.append(review)
                else:
                    break

        review_amount = len(review_list)
        count_per_page = 4

        pages: list[discord.Embed] = []
        page = discord.Embed(
            title="ReviewDB Server Reviews",
            description=f"There {'are' if review_amount > 1 else 'is'} **{review_amount} review{'s' if review_amount > 1 else ''}** for this server.",
            color=Color.random(),
        )
        page.set_author(
            name=ctx.guild.name,
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )

        for i, review in enumerate(review_list, start=1):
            page.add_field(
                name=f"{i}. @{discord.utils.escape_markdown(review['sender']['username'])} - <t:{review['timestamp']}:d>",
                value=f"{review['comment'] if len(review['comment']) <= 1024 else review['comment'][:1021] + '...'}",
                inline=False,
            )

            if i % count_per_page == 0 or i == review_amount:
                pages.append(page)
                page = discord.Embed(
                    title="ReviewDB Server Reviews",
                    description=f"There {'are' if review_amount > 1 else 'is'} **{review_amount} review{'s' if review_amount > 1 else ''}** for this server.",
                    color=Color.random(),
                )
                page.set_author(
                    name=ctx.guild.name,
                    icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
                )

        pages[0].set_footer(
            text=f"Controlling: @{ctx.author.name}" if len(pages) > 1 else f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        if len(pages) > 1:
            view = PaginationView(embeds=pages, timeout=180)
            await ctx.reply(embed=pages[0], view=view)
        else:
            await ctx.reply(embed=pages[0])


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(ReviewsCommandsCog(bot))
