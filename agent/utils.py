from typing import Any, Optional


def truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


def first_query_value(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return str(raw[0]) if raw else None
    return str(raw)
