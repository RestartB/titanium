from enum import StrEnum


class EventType(StrEnum):
    MUTE_REFRESH = "mute_refresh"
    PERMA_MUTE_REFRESH = "perma_mute_refresh"
    CLOSE_MUTE = "close_mute"
    UNBAN = "unban"
