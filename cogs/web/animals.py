import os
import random
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import Colour, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class AnimalCommandsCog(commands.GroupCog, group_name="animals", description="See cute animals."):
    REQUEST_HEADERS = {
        "User-Agent": os.getenv("REQUEST_USER_AGENT", ""),
    }

    CAT_TITLES = [
        "🐱 Aww!",
        "🐱 Cute cat!",
        "🐱 Adorable!",
        "🐱 Meow!",
        "🐱 Mrow!",
        "🐱 Mrrp!",
        "🐱 Purrfect!",
        "🐱 Cat!",
        "🐱 :3",
    ]

    DOG_TITLES = [
        "🐶 Aww!",
        "🐶 Cute dog!",
        "🐶 Adorable!",
        "🐶 Woof!",
        "🐶 Woof woof!",
        "🐶 Dog!",
        "🐶 Bark!",
    ]

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    # Cat command
    @commands.hybrid_command(name="cat", description="Get a random cat picture.")
    @commands.cooldown(1, 5)
    async def cat(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.thecatapi.com/v1/images/search", headers=self.REQUEST_HEADERS
            ) as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} Error",
                        description="The service has been rate limited. Try again later.",
                        colour=Colour.red(),
                    )
                    await ctx.reply(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.CAT_TITLES)

        embed = discord.Embed(title=embed_title, colour=Colour.light_grey())
        embed.set_image(url=request_data[0]["url"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Dog command
    @commands.hybrid_command(name="dog", description="Get a random dog picture.")
    @commands.cooldown(1, 5)
    async def dog(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://dog.ceo/api/breeds/image/random", headers=self.REQUEST_HEADERS
            ) as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} Error",
                        description="The service has been rate limited. Try again later.",
                        colour=Colour.red(),
                    )
                    await ctx.reply(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.DOG_TITLES)

        embed = discord.Embed(title=embed_title, colour=Colour.light_grey())
        embed.set_image(url=request_data["message"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Sand Cat command
    @commands.hybrid_command(name="sandcat", description="Get a random sand cat picture.")
    @commands.cooldown(1, 5)
    async def sand_cat(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        request_data = {}
        request_data["filename"] = ""

        # Check if image is a valid file type
        while not str(request_data["filename"]).endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".gif")
        ):
            # Fetch image
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://sandcat.link/api/json/", headers=self.REQUEST_HEADERS
                ) as request:
                    if request.status == 429:
                        embed = discord.Embed(
                            title=f"{self.bot.error_emoji} Error",
                            description="The service has been rate limited. Try again later.",
                            colour=Colour.red(),
                        )
                        await ctx.reply(embed=embed)
                        return
                    elif request.status == 522:
                        embed = discord.Embed(
                            title=f"{self.bot.error_emoji} Error",
                            description="The service timed out. Try again later.",
                            colour=Colour.red(),
                        )
                        await ctx.reply(embed=embed)
                        return
                    else:
                        request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.CAT_TITLES)

        embed = discord.Embed(
            title=embed_title,
            description=f"Source: [sandcat.link]({request_data['url']})",
            colour=Colour.light_grey(),
        )
        embed.set_image(url=request_data["url"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AnimalCommandsCog(bot))
