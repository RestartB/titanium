from enum import Enum


class BouncerCriteriaType(Enum):
    USERNAME = "username"
    TAG = "tag"
    AGE = "age"
    AVATAR = "avatar"


class BouncerActionType(Enum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    RESET_NICK = "reset_nick"
    ADD_ROLE = "add_role"
    REMOVE_ROLE = "remove_role"
    TOGGLE_ROLE = "toggle_role"
