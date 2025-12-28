import logging
import os
import traceback
import uuid
from typing import TYPE_CHECKING, Optional

import discord

from lib.sql.sql import ErrorLog, get_session

if TYPE_CHECKING:
    from main import TitaniumBot


async def log_error(
    bot: TitaniumBot,
    module: str,
    guild_id: Optional[int],
    error: str,
    details: str = "",
    user: discord.User | discord.Member | None = None,
    exc: Optional[Exception] = None,
    store_err: bool = True,
    send_webhook: bool = True,
) -> uuid.UUID:
    """Log an error message.

    Args:
        module (str): The module where the error occurred.
        guild_id (int): The guild ID where the error occurred.
        error (str): The error message.
        details (str, optional): Additional details about the error.
        exc (Exception, optional): The exception that was raised.
        store_err (bool, optional): Whether to store the error in the log.
    """

    uuid_id = uuid.uuid4()

    logging.error(
        f"[{uuid_id}] [Guild ID: {guild_id}] [Module: {module}] {error} Details: {details}",
        exc_info=exc,
    )

    if store_err and guild_id is not None:
        async with get_session() as session:
            error_log = ErrorLog(
                id=uuid_id,
                module=module,
                guild_id=guild_id,
                error=error,
                details=details,
            )
            session.add(error_log)

    if not send_webhook:
        return uuid_id

    embed = discord.Embed(
        title=error,
        description=f"{f'{details}\n\n' if details else ''}{f'```python\n{traceback.format_exception(exc) if exc else ""}```' if exc else ''}",
        color=discord.Colour.red(),
    )

    embed.add_field(name="Module", value=module)
    embed.add_field(name="Guild ID", value=f"`{guild_id}`")
    embed.add_field(name="Error ID", value=f"`{uuid_id}`")

    if user:
        embed.add_field(name="User", value=f"{user.mention} (`@{user.name}`, `{user.id}`)")

    if bot.user:
        embed.set_author(
            name=f"{bot.user.name}#{bot.user.discriminator}", icon_url=bot.user.display_avatar.url
        )

    webhook_url = os.getenv("ERROR_WEBHOOK")
    if webhook_url:
        webhook = discord.Webhook.from_url(
            webhook_url,
            client=bot,
        )
        await webhook.send(embed=embed)

    return uuid_id
