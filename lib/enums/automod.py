from enum import StrEnum


class AutomodRuleType(StrEnum):
    BADWORD_DETECTION = "badword_detection"
    SPAM_DETECTION = "spam_detection"
    MALICIOUS_LINK = "malicious_link"
    PHISHING_LINK = "phishing_link"


class AutomodAntispamType(StrEnum):
    MESSAGE = "message"
    MENTION = "mention"
    WORD = "word"
    NEWLINE = "newline"
    LINK = "link"
    ATTACHMENT = "attachment"
    EMOJI = "emoji"


class AutomodActionType(StrEnum):
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    DELETE = "delete"
    ADD_ROLE = "add_role"
    REMOVE_ROLE = "remove_role"
    TOGGLE_ROLE = "toggle_role"
    SEND_MESSAGE = "send_message"
