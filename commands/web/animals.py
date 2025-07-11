import random

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands


class ImageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message: discord.InteractionMessage

    # On timeout
    async def on_timeout(self):
        await self.message.edit(view=None)

    @discord.ui.button(label="Reload", emoji="🔄", style=discord.ButtonStyle.primary)
    async def reload(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        await interaction.edit_original_response(
            embed=interaction.message.embeds[0], view=None
        )


class Animals(commands.Cog):
    # noinspection SpellCheckingInspection
    def __init__(self, bot):
        self.bot = bot

        self.cat_titles = [
            "Aww!",
            "Cute cat!",
            "Adorable!",
            "Meow!",
            "Mrow!",
            "Mrrp!",
            "Purrfect!",
            "Cat!",
            ":3",
        ]
        self.dog_titles = [
            "Aww!",
            "Cute dog!",
            "Adorable!",
            "Woof!",
            "Woof woof!",
            "Dog!",
            "Bark!",
        ]

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    animalGroup = app_commands.Group(
        name="animals",
        description="See cute animals.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # Cat command
    # noinspection SpellCheckingInspection
    @animalGroup.command(name="cat", description="Get a random cat picture.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def cat(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.thecatapi.com/v1/images/search"
            ) as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title="The service has been rate limited. Try again later.",
                        color=Color.red(),
                    )
                    await interaction.followup.send(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.cat_titles)

        embed = discord.Embed(title=embed_title, color=Color.random())
        embed.set_image(url=request_data[0]["url"])
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Dog command
    # noinspection SpellCheckingInspection
    @animalGroup.command(name="dog", description="Get a random dog picture.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def dog(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

        # Fetch image
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://dog.ceo/api/breeds/image/random"
            ) as request:
                if request.status == 429:
                    embed = discord.Embed(
                        title="The service has been rate limited. Try again later.",
                        color=Color.red(),
                    )
                    await interaction.followup.send(embed=embed)
                    return
                else:
                    request_data = await request.json()

        # Create and send embed
        embed_title = random.choice(self.dog_titles)

        embed = discord.Embed(title=embed_title, color=Color.random())
        embed.set_image(url=request_data["message"])
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Sand Cat command
    # noinspection SpellCheckingInspection
    @animalGroup.command(name="sand-cat", description="Get a random sand cat picture.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    @app_commands.checks.cooldown(1, 5)
    async def sand_cat(self, interaction: discord.Interaction, ephemeral: bool = False):
        await interaction.response.defer(ephemeral=ephemeral)

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
                            title="The service has been rate limited. Try again later.",
                            color=Color.red(),
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    elif request.status == 522:
                        embed = discord.Embed(
                            title="The service timed out. Try again later.",
                            color=Color.red(),
                        )
                        await interaction.followup.send(embed=embed)
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
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        view_instance = ImageView()

        await interaction.followup.send(
            embed=embed, ephemeral=ephemeral, view=view_instance
        )
        view_instance.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Animals(bot))
