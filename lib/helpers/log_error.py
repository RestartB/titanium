import logging
import uuid
from typing import Optional

from lib.sql.sql import ErrorLog, get_session


async def log_error(
    module: str,
    guild_id: Optional[int],
    error: str,
    details: str = "",
    exc: Optional[Exception] = None,
    store_err: bool = True,
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
            await session.commit()

    return uuid_id
