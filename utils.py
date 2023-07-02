import re


def slug(input_string: str) -> str:
    # Remove non-word characters (everything except numbers and letters)
    s = re.sub(r"[^\w\s]", '', input_string)
    # Replace all runs of whitespace with a single dash
    s = re.sub(r"\s+", '-', s)
    return s.lower()
