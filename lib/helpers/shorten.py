def shorten_preserve(text: str, width: int, placeholder: str = "...") -> str:
    if len(text) <= width:
        return text
    cut = max(0, width - len(placeholder))
    return text[:cut] + placeholder
