import logging
import random
from typing import TYPE_CHECKING, Literal

from discord import Colour, Embed, Member, User, app_commands
from discord.ext import commands
from sqlalchemy import select

from lib.enums.games import GameTypes
from lib.sql.sql import GameStat, get_session

if TYPE_CHECKING:
    from main import TitaniumBot

logger: logging.Logger = logging.getLogger("games")


class GameCog(commands.Cog, name="Games", description="Play various simple games."):
    def __init__(self, bot: TitaniumBot) -> None:
        self.bot: TitaniumBot = bot

    @commands.hybrid_group(name="game", description="Game related commands.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def game_group(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    @game_group.command(
        name="stats", aliases=["stat"], description="Get stats for games that you've played."
    )
    @app_commands.describe(user="The user to get game stats for.")
    async def game_stats(
        self,
        ctx: commands.Context["TitaniumBot"],
        user: Member | User = commands.Author,
    ) -> None:
        """Get the all games stats, How many times they played, and win"""
        await ctx.defer()

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
            colour=Colour.light_gray(),
        )
        embed.set_author(name=f"@{user.name}", icon_url=user.display_avatar)
        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)

        await ctx.reply(embed=embed)

    @game_group.command(name="dice", description="Roll a dice and guess the number.")
    @app_commands.describe(guess="Your guess, between 1 and 6.")
    async def dice_game(
        self, ctx: commands.Context["TitaniumBot"], guess: commands.Range[int, 1, 6]
    ) -> None:
        """Dice roll game."""

        await ctx.defer()

        roll = random.randint(1, 6)
        win = roll == guess
        setattr(ctx, "win", win)

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

        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @game_group.command(name="coin-flip", description="Flip a coin and guess the side.")
    @app_commands.describe(choice="Your guess between heads and tails.")
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Heads", value="heads"),
            app_commands.Choice(name="Tails", value="tails"),
        ],
    )
    async def coin_flip_game(
        self,
        ctx: commands.Context["TitaniumBot"],
        choice: Literal["heads", "tails"],
    ) -> None:
        """Coin flip game."""
        await ctx.defer()

        flip_result = random.choice(["heads", "tails"])
        win = choice == flip_result
        setattr(ctx, "win", win)

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

        embed.set_footer(text=f"@{ctx.author.name}", icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @dice_game.after_invoke
    @coin_flip_game.after_invoke
    async def game_after_execute(self, ctx: commands.Context["TitaniumBot"]) -> None:
        """Update stats after the game finishes."""
        win = getattr(ctx, "win", False)

        if not ctx.command:
            return

        async with get_session() as session:
            session.add(
                GameStat(
                    user_id=ctx.author.id,
                    game=GameTypes.DICE if ctx.command.name == "dice" else GameTypes.COIN,
                    won=win,
                )
            )


async def setup(bot: TitaniumBot) -> None:
    await bot.add_cog(GameCog(bot))
