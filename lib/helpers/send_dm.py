import discord
from discord.ui import View

from lib.embeds.dm_notifs import jump_button
from lib.helpers.log_error import log_error


async def send_dm(
    embed: discord.Embed,
    user: discord.User | discord.Member,
    source_guild: discord.Guild,
    module: str = "DMs",
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

        await log_error(
            module=module,
            guild_id=source_guild.id,
            error=f"Can't send DM to @{user.name} ({user.id}) (DMs disabled)",
        )
    except discord.HTTPException as e:
        dm_success = False
        dm_error = "Failed to send DM."

        await log_error(
            module=module,
            guild_id=source_guild.id,
            error=f"Unknown Discord error while DMing @{user.name} ({user.id})",
            details=e.text,
        )
    except Exception as e:
        dm_success = False
        dm_error = "An unexpected error occurred."

        await log_error(
            module=module,
            guild_id=source_guild.id,
            error=f"Unexpected error while DMing @{user.name} ({user.id})",
            details=str(e),
        )

    return dm_success, dm_error
