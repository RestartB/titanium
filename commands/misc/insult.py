import random

import discord
from discord import Color, app_commands
from discord.ext import commands


class Insult(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Insult Command
    @app_commands.command(name="insult", description="Insult a user of your selection.")
    @app_commands.checks.cooldown(1, 10)
    @app_commands.describe(user="The user to insult.")
    @app_commands.describe(
        ping="Optional: whether to ping the user or not. Defaults to true."
    )
    async def insult(
        self, interaction: discord.Interaction, user: discord.User, ping: bool = True
    ):
        await interaction.response.defer()

        # First parts of insult
        first = [
            "lily livered",
            "jabbermouthed",
            "unkept",
            "uncultured",
            "incompetent",
            "belch-inducing",
            "bottom-of-the-barrel",
            "sly-eyed",
            "dim-bulbed",
            "unwitty",
            "spineless",
            "fruitshop-owning",
            "pickle-enjoying",
            "inconceivably impudent",
            "buck-toothed",
            "gravel-munching",
            "head-aching",
            "Migraine-making",
            "soulsucking",
            "convexly formed",
            "concavely skulled",
            "ever-spiralling",
            "constant-chatting",
            "jibber-jabbering",
            "whimsical",
            "anomalous",
            "inhuman",
            "Triassic-dwelling",
            "mentally inconclusive",
            "artifact-crunching",
            "MONSTER-drinking",
            "kidney stone-having",
            "impulsive",
            "ill-minded",
            "Gerbil-slurping",
            "Lab-grown",
            "4GB RAM-having",
            "Forehead-bigger-than-Frye-from-Splatoon 3-bearing",
            "vegetative",
            "Not-Vegeta-being",
            "sonstantly-referencing",
            "ceaselessly-communicating",
            "wet-socked",
        ]

        # Last part of insult
        last = [
            "Snake",
            "Rat",
            "inconvenience",
            "Mollusc",
            "Sea Slug",
            "Robloxian",
            "Amoeba",
            "Guinea pig",
            "fowl",
            "Mega-Maw",
            "migraine-maker",
            "Jester",
            "Rabbit puncher",
            "jabberwocky",
            "specimen",
            "Illager",
            "Bathtub",
            "Septic Tank",
            "[REDACTED]",
            "financial drain",
            "Nightcore enjoyer",
            "Fossil chomper",
            "Scrub Daddy hater",
            "Transmission vector",
            "VC goblin",
            "Mould gobbler",
            "never-thinker",
            "Orphan thrower",
            "Failed Experiment",
            "Customer Service Worker",
            "Retail Worker",
            "McDonald's slave",
            "AWP sweat",
            "Spinbotter",
            "'Good shot, mate!' spammer",
            "Goblin Shark",
            "Goon",
            "Nerd",
        ]

        # Ensure the two parts are different
        firstword, secondword = random.choice(first), random.choice(first)
        while firstword == secondword:
            secondword = random.choice(first)

        embed = discord.Embed(
            title="Insult",
            description=f"{user.mention}, you are a **{firstword}, {secondword} {random.choice(last)}!**",
            color=Color.red(),
        )

        embed.set_author(
            name=f"{user.display_name} (@{user.name})",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.followup.send(
            content=(user.mention if ping else ""), embed=embed
        )


async def setup(bot):
    await bot.add_cog(Insult(bot))
