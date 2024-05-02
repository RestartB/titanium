import discord
from discord import app_commands, Color
from discord.ext import commands
import random
import aiohttp

class animals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    global cat_titles, dog_titles
    
    animalGroup = app_commands.Group(name="animals", description="See cute animals.")
    
    # Cat / Dog Embed Titles
    cat_titles = ["Aww!", "Cute cat!", "Adorable!", "Meow!", "Purrfect!", "Cat!", ":3"]
    dog_titles = ["Aww!", "Cute dog!", "Adorable!", "Woof!", "Woof woof!", "Dog!", "Bark!"]
    
    # Cat command
    @animalGroup.command(name = "cat", description = "Get a random cat picture.")
    @app_commands.checks.cooldown(1, 5)
    async def cat(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as request:
                request_data = await request.json()
                embed_title = random.choice(cat_titles)
                embed = discord.Embed(title = embed_title, color = Color.random())
                embed.set_image(url = request_data[0]["url"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)

    # Dog command
    @animalGroup.command(name = "dog", description = "Get a random dog picture.")
    @app_commands.checks.cooldown(1, 5)
    async def dog(self, interaction: discord.Interaction):
        await interaction.response.defer()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as request:
                request_data = await request.json()
                embed_title = random.choice(dog_titles)
                embed = discord.Embed(title = embed_title, color = Color.random())
                embed.set_image(url = request_data["message"])
                embed.set_footer(text = f"Requested by {interaction.user.name}", icon_url = interaction.user.avatar.url)
                await interaction.followup.send(embed = embed)

async def setup(bot):
    await bot.add_cog(animals(bot))