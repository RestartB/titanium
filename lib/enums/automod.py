from enum import Enum


class AutomodRuleType(Enum):
    BADWORD_DETECTION = "badword_detection"
    SPAM_DETECTION = "spam_detection"
    MALICIOUS_LINK = "malicious_link"
    PHISHING_LINK = "phishing_link"


class AutomodAntispamType(Enum):
    MESSAGE = "message"
    MENTION = "mention"
    WORD = "word"
    NEWLINE = "newline"
    LINK = "link"
    ATTACHMENT = "attachment"
    EMOJI = "emoji"


class AutomodActionType(Enum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    DELETE = "delete"
    ADD_ROLE = "add_role"
    REMOVE_ROLE = "remove_role"
    TOGGLE_ROLE = "toggle_role"
    SEND_MESSAGE = "send_message"
