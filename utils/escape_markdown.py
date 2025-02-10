import re


async def escape_markdown(text: str) -> str:
    return re.sub(r"([_*~`])", r"\\\1", text)
