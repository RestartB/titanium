from dataclasses import dataclass
from io import BytesIO

import discord

from lib.enums.images import ImageFormats


@dataclass
class QuoteData:
    content: str
    user: discord.User | discord.Member
    runner_user: discord.User | discord.Member
    output_format: ImageFormats

    pfp_data: BytesIO

    nickname: bool = True
    fade: bool = True
    light_mode: bool = False
    bw_mode: bool = False
    spoiler: bool = False

    custom_quote: bool = False