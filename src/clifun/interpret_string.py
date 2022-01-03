import datetime as dt
from typing import Any, Dict, Callable, TypeVar, Type, Optional, Union, overload

from .tools import T, is_optional, unwrap_optional


class InterpretationError(ValueError):
    def __init__(self, s: str, t: T):
        self.s = s
        self.t = t

    def __str__(self):
        return f"Could not interpret '{self.s}' as {self.t}"

def interpret_bool(s: str) -> bool:
    if s.lower() in {"t", "true", "yes", "y"}:
        return True
    elif s.lower() in {"f", "false", "no", "n"}:
        return False
    else:
        raise InterpretationError(s, bool)


def interpret_datetime(s: str) -> dt.datetime:
    if hasattr(dt.datetime, "fromisoformat"):
        return dt.datetime.fromisoformat(s)
    else:
        # for python 3.6 where `fromisoformat` doesn't exist
        import isodate  # type: ignore

        return isodate.parse_datetime(s)


def interpret_date(s: str) -> dt.date:
    return dt.date(*[int(i) for i in s.split("-")])


StringInterpreters = Dict[Type[T], Callable[[str], T]]


def default_string_interpreters() -> StringInterpreters:
    return {
        int: int,
        float: float,
        str: str,
        bool: interpret_bool,
        dt.datetime: interpret_datetime,
        dt.date: interpret_date,
    }


def interpret_string_as_type(
    s: str, t: Type[T], type_converters: StringInterpreters
) -> T:
    try:
        return (
            type_converters[unwrap_optional(t)](s)
            if is_optional(t)
            else type_converters[t](s)
        )
    except KeyError:
        raise InterpretationError(s, t)
