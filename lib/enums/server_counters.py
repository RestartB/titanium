from enum import Enum


class ServerCounterType(Enum):
    TOTAL_MEMBERS = "total_members"
    USERS = "users"
    BOTS = "bots"
    ONLINE_MEMBERS = "online_members"
    MEMBERS_STATUS_ONLINE = "members_status_online"
    MEMBERS_STATUS_IDLE = "members_status_idle"
    MEMBERS_STATUS_DND = "members_status_dnd"
    MEMBERS_ACTIVITY = "members_activity"
    MEMBERS_CUSTOM_STATUS = "members_custom_status"
    OFFLINE_MEMBERS = "offline_members"
    CHANNELS = "channels"
    ACTIVITY = "activity"
