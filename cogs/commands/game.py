import logging
import random
from typing import TYPE_CHECKING, Literal

import discord
from discord import Colour, Embed, Member, User, app_commands
from discord.ext import commands
from sqlalchemy import select

from lib.enums.games import GameTypes
from lib.sql.sql import GameStat, get_session

if TYPE_CHECKING:
    from main import TitaniumBot

logger: logging.Logger = logging.getLogger("games")


@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class GameCog(commands.GroupCog, group_name="game", description="Game related commands."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    async def __update_stats(
        self, interaction: discord.Interaction, game: Literal["dice", "coin"], won: bool
    ) -> None:
        if interaction.user.id in self.bot.opt_out:
            return

        async with get_session() as session:
            session.add(
                GameStat(
                    user_id=interaction.user.id,
                    game=GameTypes.DICE if game == "dice" else GameTypes.COIN,
                    won=won,
                )
            )

    # TODO: check that commands.Author works here
    @app_commands.command(name="stats", description="Get stats for games that you've played.")
    @app_commands.describe(
        user="The user to get game stats for.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 5)
    async def game_stats(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        user: Member | User = commands.Author,
        ephemeral: bool = False,
    ) -> None:
        """Get the all games stats, How many times they played, and win"""
        await interaction.response.defer(ephemeral=ephemeral)

        if interaction.user.id in self.bot.opt_out:
            embed = Embed(
                title=f"{self.bot.error_emoji} Opted Out",
                description="This user has opted out of optional data collection and cannot use game statistic tracking.",
                colour=Colour.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return

        async with get_session() as session:
            stmt = select(GameStat).where(GameStat.user_id == user.id)
            result = await session.execute(stmt)
            stats = result.scalars().all()

        dice_games = list(filter(lambda x: x.game == GameTypes.DICE, stats))
        coin_games = list(filter(lambda x: x.game == GameTypes.COIN, stats))

        embed = Embed(
            title="Game Stats",
            description=f"**🎲 Dice Roll:** won **{sum(1 for game in dice_games if game.won)}** games, lost **{sum(1 for game in dice_games if not game.won)}** games\n"
            f"**🪙 Coin Flip:** won **{sum(1 for game in coin_games if game.won)}** games, lost **{sum(1 for game in coin_games if not game.won)}** games",
            colour=Colour.light_grey(),
        )
        embed.set_author(name=f"@{user.name}", icon_url=user.display_avatar)
        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )

        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="dice", description="Roll a dice and guess the number.")
    @app_commands.describe(
        guess="Your guess, between 1 and 6.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.checks.cooldown(1, 3)
    async def dice_game(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        guess: app_commands.Range[int, 1, 6],
        ephemeral: bool = False,
    ) -> None:
        """Dice roll game."""

        await interaction.response.defer(ephemeral=ephemeral)

        roll = random.randint(1, 6)
        win = roll == guess
        await self.__update_stats(interaction, "dice", win)

        if win:
            embed = Embed(
                colour=Colour.green(),
                title=f"{self.bot.success_emoji} You Win",
                description=f"🎲 You guessed `{guess}` and rolled `{roll}`!",
            )
        else:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} You Lost",
                description=f"🎲 You guessed `{guess}`, but rolled `{roll}`!",
            )

        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @app_commands.command(name="coin-flip", description="Flip a coin and guess the side.")
    @app_commands.describe(
        choice="Your guess between heads and tails.",
        ephemeral="Optional: whether to send the command output as a dismissible message only visible to you. Defaults to false.",
    )
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Heads", value="heads"),
            app_commands.Choice(name="Tails", value="tails"),
        ],
    )
    @app_commands.checks.cooldown(1, 3)
    async def coin_flip_game(
        self,
        interaction: discord.Interaction["TitaniumBot"],
        choice: Literal["heads", "tails"],
        ephemeral: bool = False,
    ) -> None:
        """Coin flip game."""
        await interaction.response.defer(ephemeral=ephemeral)

        flip_result = random.choice(["heads", "tails"])
        win = choice == flip_result
        await self.__update_stats(interaction, "coin", win)

        if win:
            embed = Embed(
                colour=Colour.green(),
                title=f"{self.bot.success_emoji} You Won",
                description=f"🪙 You chose **{choice}** and the coin landed on **{flip_result}**!",
            )
        else:
            embed = Embed(
                colour=Colour.red(),
                title=f"{self.bot.error_emoji} You Lost",
                description=f"🪙 You chose **{choice}**, but the coin landed on **{flip_result}**!",
            )

        embed.set_footer(
            text=f"@{interaction.user.name}", icon_url=interaction.user.display_avatar.url
        )
        await interaction.followup.send(embed=embed, ephemeral=ephemeral)


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(GameCog(bot))
