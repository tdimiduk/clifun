import datetime as dt
from dataclasses import dataclass
from typing import Optional


import clifun


@dataclass(frozen=True)
class Foo:
    a: dt.datetime
    b: Optional[str] = None


@dataclass(frozen=True)
class Bar:
    f: Foo
    c: int


if __name__ == "__main__":
    bar = clifun.call(Bar)
    print(bar)
