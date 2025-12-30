from enum import Enum


class ServerCounterType(Enum):
    TOTAL_MEMBERS = "total_members"
    USERS = "users"
    BOTS = "bots"
    ONLINE_MEMBERS = "online_members"
    OFFLINE_MEMBERS = "offline_members"
    CHANNELS = "channels"
    CATEGORIES = "categories"
    ROLES = "roles"
    TOTAL_XP = "total_xp"