from datetime import datetime


class AntiSpamMessage:
    user_id: int
    message_id: int
    channel_id: int
    mention_count: int
    word_count: int
    newline_count: int
    link_count: int
    attachment_count: int
    emoji_count: int
    timestamp: datetime
