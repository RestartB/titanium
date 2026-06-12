from typing import TYPE_CHECKING

from discord import Colour, Embed

if TYPE_CHECKING:
    from main import TitaniumBot


def reminder_deleted(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Reminder Deleted",
        description="The reminder has been successfully deleted.",
        colour=Colour.green(),
    )


def reminder_edited(bot: TitaniumBot) -> Embed:
    return Embed(
        title=f"{bot.success_emoji} Reminder Edited",
        description="The reminder has been successfully edited.",
        colour=Colour.green(),
    )
