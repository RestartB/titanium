import discord
from discord.ui import View

from lib.embeds.dm_notifs import jump_button


async def send_dm(
    embed: discord.Embed,
    user: discord.User | discord.Member,
    source_guild: discord.Guild,
) -> tuple[bool, str]:
    dm_success = True
    dm_error = ""

    try:
        await user.send(
            embed=embed,
            view=View().add_item(jump_button(source_guild)),
        )
    except discord.Forbidden:
        dm_success = False
        dm_error = "User has DMs disabled."
    except discord.HTTPException:
        dm_success = False
        dm_error = "Failed to send DM."

    return dm_success, dm_error
