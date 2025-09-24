import logging
import logging.handlers
import os


def setup_logging(
    log_file: str = "logs/titanium.log", mode: str = "INFO", file_backup: int = 5
) -> None:
    """
    Configures logging for the bot including file and console handlers.

    Parameters
    ----------
    log_file : str, optional
        Path to the log file. Defaults to "logs".
    mode : str, optional
        Logging level as a string (e.g., "INFO", "DEBUG"). Defaults to "INFO".
    file_backup : int, optional
        Number of backup log files to keep. Defaults to 5.

    Returns
    -------
    None
    """

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    log_level = getattr(logging, mode.upper(), logging.INFO)

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    fmt = "[{asctime}] [{levelname:<8}] [{name}]: {message}"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=dt_fmt,
        style="{",
    )

    root_logger = logging.getLogger()

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        encoding="utf-8",
        maxBytes=20 * 1024 * 1024,  # 20 MB
        backupCount=file_backup,
    )
    file_handler.setFormatter(logging.Formatter(fmt, dt_fmt, style="{"))

    if root_logger.handlers:
        root_logger.handlers[0].setFormatter(logging.Formatter(fmt, dt_fmt, style="{"))

    root_logger.addHandler(file_handler)

    for noisy_logger in ["discord", "discord.gateway"]:
        logger = logging.getLogger(noisy_logger)
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
