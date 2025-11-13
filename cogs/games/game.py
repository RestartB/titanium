import logging
import random
from typing import TYPE_CHECKING, Literal

from discord import Colour, Embed, Member, User, app_commands
from discord.ext import commands
from sqlalchemy import select

from lib.sql.sql import Game, GameStat, get_session

if TYPE_CHECKING:
    from main import TitaniumBot

logger: logging.Logger = logging.getLogger("games")


class GameCog(commands.Cog, name="Games", description="Play various simple games."):
    def __init__(self, bot: "TitaniumBot") -> None:
        self.bot: "TitaniumBot" = bot
        self.game_cache: dict[str, int] = {}
        self.available_games: list[str] = ["dice", "coin-flip"]

    async def cog_load(self) -> None:
        """Set all the games in Game table if does not exist yet."""
        async with get_session() as session:
            stmt = select(Game.name)
            result = await session.execute(stmt)
            existing_games = {row[0] for row in result.all()}
            for game_name in self.available_games:
                if game_name not in existing_games:
                    session.add(Game(name=game_name))

            await session.commit()

        await self.load_game_cache()
        logger.info("Game table cache loaded")

    async def load_game_cache(self) -> None:
        """Load the game cache initially to reduce the DB call."""
        stmt = select(Game)
        async with get_session() as session:
            result = await session.execute(stmt)
            games = result.scalars().all()
            self.game_cache = {g.name: g.id for g in games}

    @commands.hybrid_group(name="game", description="Game related command group.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def game(self, ctx: commands.Context["TitaniumBot"]) -> None:
        raise commands.CommandNotFound

    @game.command(name="stats", aliases=["stat"], description="Get the all games stats.")
    @app_commands.describe(user="Whos game stats to be show.")
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

        user_stats = {s.game_id: (s.played, s.win) for s in stats}

        lines = []
        for game_name in self.available_games:
            gid = self.game_cache.get(game_name)

            if gid:
                played, win = user_stats.get(gid, (0, 0))
                lines.append(f"- **{game_name.capitalize()}** → Played: `{played}` | Wins: `{win}`")

        embed = Embed(
            title="Game Stats",
            description="\n".join(lines),
            color=Colour.blue(),
        )
        await ctx.reply(embed=embed)

    @game.command(name="dice", description="Roll a dice and try your luck!")
    @app_commands.describe(guess="Guess the dice number.")
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
                color=Colour.green(),
                title=f"{self.bot.success_emoji} You Win",
                description=f"🎲 You guessed `{guess}` and rolled `{roll}`!",
            )
        else:
            embed = Embed(
                color=Colour.red(),
                title=f"{self.bot.error_emoji} You Lost",
                description=f"🎲 You guessed `{guess}`, but rolled `{roll}`!",
            )

        await ctx.reply(embed=embed)

    @game.command(name="coin-flip", description="Flip a coin!")
    @app_commands.describe(choice="Guess the coin side (Head or Tails)")
    async def coin_flip_game(
        self,
        ctx: commands.Context["TitaniumBot"],
        choice: Literal["Head", "Tails"],
    ) -> None:
        """Coin flip game."""
        await ctx.defer()

        user_choice = choice.lower()
        if user_choice not in ["head", "tails"]:
            embed = Embed(
                color=Colour.red(),
                title="Invalid Choice",
                description="Please pick **Head** or **Tails**.",
            )
            setattr(ctx, "valid_invoke", False)  # setting this so we dont inc the played by +1
            await ctx.reply(embed=embed)

            return

        flip_result = random.choice(["head", "tails"])
        win = user_choice == flip_result
        setattr(ctx, "win", win)

        if win:
            embed = Embed(
                color=Colour.green(),
                title=f"{self.bot.success_emoji} You Won",
                description=f"🪙 You chose **{choice}** and the coin landed on **{flip_result.title()}**!",
            )
        else:
            embed = Embed(
                color=Colour.red(),
                title=f"{self.bot.error_emoji} You Lost",
                description=f"🪙 You chose **{choice}**, but the coin landed on **{flip_result.title()}**!",
            )
        await ctx.reply(embed=embed)

    @dice_game.after_invoke
    @coin_flip_game.after_invoke
    async def game_after_execute(self, ctx: commands.Context["TitaniumBot"]) -> None:
        """Update stats after the game finishes."""
        win = getattr(ctx, "win", False)

        valid_invoke: bool = getattr(
            ctx, "valid_invoke", True
        )  # if arg parse failed then we can set the, by defualt it will be True

        if valid_invoke and ctx.command:
            await self.record_game_result(ctx.author.id, ctx.command.name, won=win)

    async def record_game_result(self, user_id: int, game_name: str, won: bool = False) -> None:
        """Insert or update a user's stats for a game."""
        game_id = self.game_cache.get(game_name)
        if not game_id:
            raise ValueError(f"Game '{game_name}' not found in cache.")

        async with get_session() as session:
            stmt = select(GameStat).where(GameStat.user_id == user_id, GameStat.game_id == game_id)
            result = await session.execute(stmt)
            stat = result.scalar_one_or_none()

            if not stat:
                stat = GameStat(user_id=user_id, game_id=game_id, played=0, win=0)
                session.add(stat)

            stat.played += 1
            if won:
                stat.win += 1

            await session.commit()


async def setup(bot: "TitaniumBot") -> None:
    await bot.add_cog(GameCog(bot))
