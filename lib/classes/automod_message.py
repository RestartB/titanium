from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AutomodMessage:
    user_id: int
    message_id: int
    channel_id: int
    triggered_word_rule_amount: dict[UUID, int]
    malicious_link_count: int
    phishing_link_count: int
    mention_count: int
    word_count: int
    newline_count: int
    link_count: int
    attachment_count: int
    emoji_count: int
    timestamp: datetime
