import re
from datetime import datetime, timedelta, timezone

from discord.ext import commands


class DurationConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> timedelta:
        multipliers = {
            "s": 1,  # seconds
            "m": 60,  # minutes
            "h": 3600,  # hours
            "d": 86400,  # days
            "w": 604800,  # weeks
            "mon": 2592000,  # months
            "y": 31536000,  # years
        }

        # Match units
        pattern = r"(\d+)(s|m|h|d|w|mon|y)"
        matches = re.findall(pattern, argument.lower())

        if not matches:
            raise commands.BadArgument(
                "Invalid time format. Use format like '1h30m' or '5d'."
            )

        total_seconds = 0
        used_units = set()

        for amount_str, unit in matches:
            if unit in used_units:
                raise commands.BadArgument(f"Duplicate time unit '{unit}' found.")

            used_units.add(unit)
            amount = int(amount_str)
            total_seconds += amount * multipliers[unit]

        # Check entire string was matched
        reconstructed = "".join(f"{amount}{unit}" for amount, unit in matches)
        if reconstructed != argument.lower():
            raise commands.BadArgument("Invalid characters in time string.")

        return timedelta(seconds=total_seconds)


def duration_to_timestring(time: datetime) -> str:
    now = datetime.now(timezone.utc)
    delta = time - now

    seconds = delta.total_seconds()
    string = ""

    if seconds >= 31536000:  # Year
        string += f"{int(seconds // 31536000)}y "
        seconds //= 31536000

    if seconds >= 2592000:  # Month
        string += f"{int(seconds // 2592000)}mon "
        seconds //= 2592000

    if seconds >= 604800:  # Week
        string += f"{int(seconds // 604800)}w "
        seconds //= 604800

    if seconds >= 86400:  # Day
        string += f"{int(seconds // 86400)}d "
        seconds //= 86400

    if seconds >= 3600:  # Hour
        string += f"{int(seconds // 3600)}h "
        seconds //= 3600

    if seconds >= 60:  # Minute
        string += f"{int(seconds // 60)}m "
        seconds //= 60

    if seconds > 0:  # Second
        string += f"{int(seconds)}s"

    return string.strip() if string else "0s"
