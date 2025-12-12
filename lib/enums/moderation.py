from enum import Enum


class CaseType(Enum):
    WARN = "warning"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"


class CaseSource(Enum):
    MODERATION = "moderation"
    AUTOMOD = "automod"
    BOUNCER = "bouncer"
