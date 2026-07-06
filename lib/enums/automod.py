from enum import StrEnum


class AutomodCriteriaType(StrEnum):
    WORD_LIST = "word_list"
    MALICIOUS_LINK = "malicious_link"
    PHISHING_LINK = "phishing_link"
    MESSAGE_SPAM = "message_spam"
    MENTION_SPAM = "mention_spam"
    WORD_SPAM = "word_spam"
    NEWLINE_SPAM = "newline_spam"
    LINK_SPAM = "link_spam"
    ATTACHMENT_SPAM = "attachment_spam"
    EMOJI_SPAM = "emoji_spam"
    DISCORD_DICE_ROLL = "discord_dice_roll"


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
