def truncate(s, length=100, suffix="..."):
    """Truncate a string to a certain length.

    Args:
        s (str): The string to truncate.
        length (int): The maximum length of the truncated string.
        suffix (str): The suffix to append to the string if it is truncated.

    Returns:
        str: The truncated string.
    """
    if len(s) > length:
        return s[: length - len(suffix)] + suffix
    return s
