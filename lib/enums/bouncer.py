from enum import StrEnum


class BouncerEventType(StrEnum):
    JOIN = "join"
    UPDATE = "update"


class BouncerCriteriaType(StrEnum):
    USERNAME = "username"
    TAG = "tag"
    AGE = "age"
    AVATAR = "avatar"


class BouncerActionType(StrEnum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    RESET_NICK = "reset_nick"
    ADD_ROLE = "add_role"
    REMOVE_ROLE = "remove_role"
    TOGGLE_ROLE = "toggle_role"
