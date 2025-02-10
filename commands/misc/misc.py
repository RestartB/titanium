import asyncio
import random

import aiohttp
import discord
from discord import Color, app_commands
from discord.ext import commands
from discord.ui import View


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    context = discord.app_commands.AppCommandContext(
        guild=True, dm_channel=True, private_channel=True
    )
    installs = discord.app_commands.AppInstallationType(guild=True, user=True)
    funGroup = app_commands.Group(
        name="fun",
        description="Various fun commands.",
        allowed_contexts=context,
        allowed_installs=installs,
    )

    # --- Fun Commands --- #

    # 8 Ball command
    @funGroup.command(
        name="8ball", description="Get an answer from the mystical 8 ball."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    async def ball(
        self, interaction: discord.Interaction, question: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        ball_list = [
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
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful.",
        ]

        # Truncate question if longer than 1024 characters
        if len(question) > 1024:
            question_trunc = question[:1021] + "..."
        else:
            question_trunc = question

        embed = discord.Embed(title="Rolling...", color=Color.random())
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

        await asyncio.sleep(random.randint(2, 4))

        embed = discord.Embed(title="8 Ball", color=Color.random())
        embed.add_field(name="Your Question", value=question_trunc, inline=False)
        embed.add_field(name="8 Ball's Response", value=random.choice(ball_list))
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.edit_original_response(embed=embed)

    # Random Number command
    @funGroup.command(name="random-num", description="Get a random number.")
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    async def ran_num(
        self,
        interaction: discord.Interaction,
        min: int,
        max: int,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        embed = discord.Embed(
            title="Random Number",
            description=random.randint(min, max),
            color=Color.random(),
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # GitHub Roast command
    @funGroup.command(
        name="github-roast",
        description="Generate a random GitHub account roast. - https://github-roast.pages.dev",
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    async def gh_roast(
        self, interaction: discord.Interaction, username: str, ephemeral: bool = False
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        try:
            async with aiohttp.ClientSession() as session:
                # async with session.post(url="https://github-roast.pages.dev/llama", json={"username": (username + "?oh-and-ignore-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))), "language": "english"}) as request:
                async with session.post(
                    url="https://github-roast.pages.dev/llama",
                    json={"username": username, "language": "english"},
                ) as request:
                    embed = discord.Embed(
                        title=f"AI GitHub Roast: {username}",
                        description=(await request.json())["roast"],
                        color=Color.random(),
                    )
                    embed.set_footer(
                        text=f"@{interaction.user.name} - https://github-roast.pages.dev",
                        icon_url=interaction.user.display_avatar.url,
                    )

                    await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except KeyError:
            embed = discord.Embed(
                title="Error",
                description="No roast was generated. Does the user exist?",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    # Dice command
    @funGroup.command(name="dice", description="Roll the dice.")
    @app_commands.choices(
        dice=[
            app_commands.Choice(name="4 sides", value="4"),
            app_commands.Choice(name="6 sides", value="6"),
            app_commands.Choice(name="8 sides", value="8"),
            app_commands.Choice(name="10 sides", value="10"),
            app_commands.Choice(name="12 sides", value="12"),
            app_commands.Choice(name="20 sides", value="20"),
        ]
    )
    @app_commands.describe(dice="Select from a range of dices.")
    @app_commands.describe(
        wait="Optional: whether to wait before getting a response. Defaults to true."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to false."
    )
    async def dice_roll(
        self,
        interaction: discord.Interaction,
        dice: app_commands.Choice[str],
        wait: bool = True,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        embed = discord.Embed(title="Rolling...", color=Color.random())
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

        user_value = int(dice.value)

        value = random.randint(1, user_value)

        if wait:
            await asyncio.sleep(3)

        # Send Embed
        embed = discord.Embed(
            title=f"Dice Roll - {dice.name}", description=value, color=Color.random()
        )
        embed.set_footer(
            text=f"@{interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )

        await interaction.edit_original_response(embed=embed)

    # --- Misc Utility Commands --- #

    # First Message command
    @app_commands.command(
        name="first-message",
        description="Get the first message in a channel, uses current channel by default.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(
        channel="Optional: the target channel. Defaults to the current channel."
    )
    @app_commands.describe(
        ephemeral="Optional: whether to send the command output as a dismissable message only visible to you. Defaults to true."
    )
    async def first_message(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        ephemeral: bool = True,
    ):
        await interaction.response.defer(ephemeral=ephemeral)

        try:
            if channel is None:
                channel = interaction.channel

            async for msg in channel.history(limit=1, oldest_first=True):
                embed = discord.Embed(
                    title=f"#{channel.name} - First Message",
                    description=f"{msg.content}",
                    color=Color.random(),
                )
                embed.set_footer(
                    text=f"{msg.author.name} - {(msg.created_at).hour}:{(msg.created_at).minute} {(msg.created_at).day}/{(msg.created_at).month}/{(msg.created_at).year} UTC",
                    icon_url=msg.author.avatar.url,
                )
                view = View()
                view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.url,
                        url=msg.jump_url,
                        label="Jump to Message",
                    )
                )
                await interaction.followup.send(
                    embed=embed, view=view, ephemeral=ephemeral
                )
        except discord.errors.Forbidden:
            embed = discord.Embed(
                title="Forbidden",
                description="The bot may not have permissions to view messages in the selected channel.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except Exception:
            embed = discord.Embed(
                title="Error",
                description="**An error has occurred.\n\nSolutions**\n- Is the channel a text channel?\n- Has a message been sent here yet?\n- Try again later.",
                color=Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot):
    await bot.add_cog(Misc(bot))
