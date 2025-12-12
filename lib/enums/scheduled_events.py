from enum import Enum


class EventType(Enum):
    MUTE_REFRESH = "mute_refresh"
    PERMA_MUTE_REFRESH = "perma_mute_refresh"
    UNBAN = "unban"
