from enum import Enum


class CaseType(Enum):
    WARN = "warning"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"