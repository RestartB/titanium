from enum import StrEnum


class CaseType(StrEnum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"


class CaseSource(StrEnum):
    MODERATION = "moderation"
    AUTOMOD = "automod"
    BOUNCER = "bouncer"
