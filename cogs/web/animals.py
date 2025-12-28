import random
from typing import TYPE_CHECKING

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands

from lib.helpers.global_alias import add_global_aliases, global_alias

if TYPE_CHECKING:
    from main import TitaniumBot


class AnimalCommandsCog(commands.Cog):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot
        add_global_aliases(self, bot)

        self.cat_titles = [
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
        self.dog_titles = [
            "🐶 Aww!",
            "🐶 Cute dog!",
            "🐶 Adorable!",
            "🐶 Woof!",
            "🐶 Woof woof!",
            "🐶 Dog!",
            "🐶 Bark!",
        ]

    @commands.hybrid_group(name="animals", description="See cute animals.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def animals_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    # Cat command
    @animals_group.command(name="cat", description="Get a random cat picture.")
    @global_alias("cat")
    @commands.cooldown(1, 5)
    async def cat(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} Error",
                        description="The service has been rate limited. Try again later.",
                        color=Color.red(),
                    )
                    await ctx.reply(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.cat_titles)

        embed = discord.Embed(title=embed_title, color=Color.random())
        embed.set_image(url=request_data[0]["url"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Dog command
    @animals_group.command(name="dog", description="Get a random dog picture.")
    @global_alias("dog")
    @commands.cooldown(1, 5)
    async def dog(self, ctx: commands.Context["TitaniumBot"]):
        await ctx.defer()

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title=f"{self.bot.error_emoji} Error",
                        description="The service has been rate limited. Try again later.",
                        color=Color.red(),
                    )
                    await ctx.reply(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.dog_titles)

        embed = discord.Embed(title=embed_title, color=Color.random())
        embed.set_image(url=request_data["message"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Sand Cat command
    @animals_group.command(name="sandcat", description="Get a random sand cat picture.")
    @global_alias("sandcat")
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
                async with session.get("https://sandcat.link/api/json/") as request:
                    if request.status == 429:
                        embed = discord.Embed(
                            title=f"{self.bot.error_emoji} Error",
                            description="The service has been rate limited. Try again later.",
                            color=Color.red(),
                        )
                        await ctx.reply(embed=embed)
                        return
                    elif request.status == 522:
                        embed = discord.Embed(
                            title=f"{self.bot.error_emoji} Error",
                            description="The service timed out. Try again later.",
                            color=Color.red(),
                        )
                        await ctx.reply(embed=embed)
                        return
                    else:
                        request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.cat_titles)

        embed = discord.Embed(
            title=embed_title,
            description=f"Source: [sandcat.link]({request_data['url']})",
            color=Color.random(),
        )
        embed.set_image(url=request_data["url"])
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(AnimalCommandsCog(bot))
