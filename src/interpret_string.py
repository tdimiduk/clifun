import datetime as dt
from typing import Any, Dict, Callable, TypeVar, Type, Optional, Union, overload

T = TypeVar("T")


class InterpretationError(ValueError):
    def __init__(self, s: str, t: T):
        self.s = s
        self.t = t

    def __str__(self):
        return f"Could not interpret '{self.s}' as {self.t}"

class StringInterpreter:
    def __init__(self, mapping: Dict[Type[T], Callable[[str], T]] = {}):
        self.mapping = mapping

    def register(self, t: Type[T], converter: Callable[[str], T]) -> None:
        self.mapping[t] = converter

    def as_type(self, s: str, t: Type[T]) -> T:
        try:
            return self.mapping[t](s)
        except KeyError:
            raise InterpretationError(s, t)

    def __contains__(self, t: T) -> bool:
        return t in self.mapping

def interpret_bool(s: str) -> bool:
    if s.lower() in {"t", "true", "yes", "y"}:
        return True
    elif s.lower() in {"f", 'false', 'no', 'n'}:
        return False
    else:
        raise InterpretationError(s, bool)


def interpret_datetime(s: str) -> dt.datetime:
      if hasattr(dt.datetime, 'fromisoformat'):
          return dt.datetime.fromisoformat(s)
      else:
          # for python 3.6 where `fromisoformat` doesn't exist
          import isodate # type: ignore
          return isodate.parse_datetime(s)

def interpret_date(s: str) -> dt.date:
    return dt.date(*[int(i) for i in s.split('-')])


interpret = StringInterpreter()
interpret.register(int, int)
interpret.register(float, float)
interpret.register(str, str)
interpret.register(bool, interpret_bool)
interpret.register(dt.datetime, interpret_datetime)
interpret.register(dt.date, interpret_date)
