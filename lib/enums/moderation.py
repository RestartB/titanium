from enum import Enum


class CaseType(Enum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"


class CaseSource(Enum):
    MODERATION = "moderation"
    AUTOMOD = "automod"
    BOUNCER = "bouncer"
