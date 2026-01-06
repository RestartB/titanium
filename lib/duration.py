from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from discord.ext import commands
from durations import Duration
from sqlalchemy import Column

if TYPE_CHECKING:
    from main import TitaniumBot


class DurationConverter(commands.Converter):
    MAX_YEARS = 60
    MAX_SECONDS = MAX_YEARS * 31536000

    async def convert(
        self, ctx: commands.Context["TitaniumBot"], argument: str
    ) -> timedelta | None:
        # Check for permanent keywords
        if argument.lower().strip() in ("permanent", "perma", "0"):
            return None

        try:
            seconds = Duration(argument).to_seconds()

            if seconds == 0:
                return None

            if seconds > self.MAX_SECONDS:
                raise commands.BadArgument(
                    f"Duration cannot exceed {self.MAX_YEARS} years. "
                    f"For permanent actions, use 'permanent', 'perma', '0', or don't provide a duration."
                )

            return timedelta(seconds=seconds)
        except OverflowError:
            raise commands.BadArgument(
                f"Duration cannot exceed {self.MAX_YEARS} years. "
                f"For permanent actions, use 'permanent', 'perma', '0', or don't provide a duration."
            )


def duration_to_timestring(
    start: datetime | Column[datetime], end: datetime | Column[datetime]
) -> str:
    delta = end - start

    seconds = delta.total_seconds()
    string = ""

    if seconds >= 31536000:  # Year
        string += f"{int(seconds // 31536000)}y "
        seconds %= 31536000

    if seconds >= 2592000:  # Month
        string += f"{int(seconds // 2592000)}mon "
        seconds %= 2592000

    if seconds >= 604800:  # Week
        string += f"{int(seconds // 604800)}w "
        seconds %= 604800

    if seconds >= 86400:  # Day
        string += f"{int(seconds // 86400)}d "
        seconds %= 86400

    if seconds >= 3600:  # Hour
        string += f"{int(seconds // 3600)}h "
        seconds %= 3600

    if seconds >= 60:  # Minute
        string += f"{int(seconds // 60)}m "
        seconds %= 60

    if seconds > 0:  # Second
        string += f"{int(seconds)}s"

    return string.strip() if string else "0s"
