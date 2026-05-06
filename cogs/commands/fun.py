import random
from typing import TYPE_CHECKING, Literal

import discord
from discord import Colour, Embed, app_commands
from discord.ext import commands

from lib.helpers.shorten import shorten_preserve

if TYPE_CHECKING:
    from main import TitaniumBot


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class FunCommandsCog(commands.GroupCog, group_name="fun", description="Fun commands."):
    """Fun commands."""

    def __init__(self, bot: TitaniumBot) -> None:
        self.bot = bot

    # 8 ball command
    @commands.hybrid_command(
        name="8ball", aliases=["8-ball"], description="Consult the mystical magic 8 ball."
    )
    @app_commands.describe(question="Optional: your question.")
    async def eight_ball(self, ctx: commands.Context["TitaniumBot"], *, question: str = "") -> None:
        await ctx.defer()

        good_responses = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes, definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
        ]
        mid_responses = [
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
        ]
        bad_responses = [
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful.",
        ]

        selection = random.randint(1, 3)
        if selection == 1:
            response = random.choice(good_responses)
            emoji = self.bot.success_emoji
            colour = Colour.green()
        elif selection == 2:
            response = random.choice(mid_responses)
            emoji = self.bot.info_emoji
            colour = Colour.light_grey()
        else:
            response = random.choice(bad_responses)
            emoji = self.bot.error_emoji
            colour = Colour.red()

        embed = Embed(
            title=f"{emoji} {response}",
            colour=colour,
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        if question:
            embed.add_field(
                name="Your Question",
                value=shorten_preserve(question, width=1024, placeholder="[...]"),
            )

        await ctx.reply(embed=embed)

    # Random number command
    @commands.hybrid_command(
        name="random-number",
        aliases=["randomnumber", "randomnum", "random-num"],
        description="Generate a random number.",
    )
    @app_commands.describe(
        minimum="The minimum number that can be generated.",
        maximum="The maximum number that can be generated.",
    )
    async def random_number(
        self, ctx: commands.Context["TitaniumBot"], minimum: int, maximum: int
    ) -> None:
        await ctx.defer()

        embed = Embed(
            title=f"{random.randint(minimum, maximum):,}",
            colour=Colour.light_grey(),
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Dice command
    @commands.hybrid_command(
        name="dice",
        description="Roll the dice.",
    )
    @app_commands.describe(
        sides="Optional: the amount of sides. Defaults to a 6 sided die.",
    )
    async def dice(
        self, ctx: commands.Context["TitaniumBot"], sides: Literal[4, 6, 8, 10, 12, 20, 100] = 6
    ) -> None:
        await ctx.defer()

        embed = Embed(
            title=f"🎲 Rolled a {random.randint(1, sides):,}",
            colour=Colour.light_grey(),
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    # Insult command
    @commands.hybrid_command(
        name="insult",
        description="Generate a savage insult for the user of your selection.",
    )
    @app_commands.describe(user="The user to insult.")
    async def insult(self, ctx: commands.Context["TitaniumBot"], user: discord.User):
        await ctx.defer()

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
            colour=Colour.red(),
        )
        embed.set_author(
            name=f"{user.display_name} (@{user.name})",
            icon_url=user.display_avatar.url,
        )
        embed.set_footer(
            text=f"@{ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.reply(embed=embed)

    freaky_map = {
        "q": "𝓺",
        "w": "𝔀",
        "e": "𝓮",
        "r": "𝓻",
        "t": "𝓽",
        "y": "𝔂",
        "u": "𝓾",
        "i": "𝓲",
        "o": "𝓸",
        "p": "𝓹",
        "a": "𝓪",
        "s": "𝓼",
        "d": "𝓭",
        "f": "𝓯",
        "g": "𝓰",
        "h": "𝓱",
        "j": "𝓳",
        "k": "𝓴",
        "l": "𝓵",
        "z": "𝔃",
        "x": "𝔁",
        "c": "𝓬",
        "v": "𝓿",
        "b": "𝓫",
        "n": "𝓷",
        "m": "𝓶",
        "Q": "𝓠",
        "W": "𝓦",
        "E": "𝓔",
        "R": "𝓡",
        "T": "𝓣",
        "Y": "𝓨",
        "U": "𝓤",
        "I": "𝓘",
        "O": "𝓞",
        "P": "𝓟",
        "A": "𝓐",
        "S": "𝓢",
        "D": "𝓓",
        "F": "𝓕",
        "G": "𝓖",
        "H": "𝓗",
        "J": "𝓙",
        "K": "𝓚",
        "L": "𝓛",
        "Z": "𝓩",
        "X": "𝓧",
        "C": "𝓒",
        "V": "𝓥",
        "B": "𝓑",
        "N": "𝓝",
        "M": "𝓜",
    }

    # Freaky Text commands
    @app_commands.command(
        name="freaky",
        description="Convert normal text to freaky text, or freaky text to normal text.",
    )
    @app_commands.describe(
        mode="The conversion mode to use.",
        text="The text to convert.",
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false.",
    )
    async def freaky(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        mode: Literal["Convert to freaky text", "Convert to normal text"],
        text: str,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        for char in self.freaky_map:
            if mode == "Convert to normal text":
                text = text.replace(self.freaky_map[char], char)
            else:
                text = text.replace(char, self.freaky_map[char])

        await interaction.followup.send(
            content=text,
            allowed_mentions=discord.AllowedMentions.none(),
            ephemeral=ephemeral,
        )

    @commands.command(
        name="freaky",
        aliases=["freakytext", "freaky-text"],
        description="Convert normal text to freaky text.",
    )
    async def freaky_prefix(self, ctx: commands.Context["TitaniumBot"], *, text: str) -> None:
        for char in self.freaky_map:
            text = text.replace(char, self.freaky_map[char])

        await ctx.reply(content=text, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(FunCommandsCog(bot))
