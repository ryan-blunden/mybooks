from typing import Any, List, Optional


def truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


def first_query_value(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return str(raw[0]) if raw else None
    return str(raw)


def flatten_exceptions(exc: BaseException) -> List[BaseException]:
    """Recursively flatten ExceptionGroup hierarchies for human-friendly error reporting."""

    if isinstance(exc, BaseExceptionGroup):
        flattened: List[BaseException] = []
        for inner in exc.exceptions:  # type: ignore[attr-defined]
            flattened.extend(flatten_exceptions(inner))
        return flattened

    return [exc]
