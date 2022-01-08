import datetime as dt
from typing import Optional

import attr

import clifun


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: dt.datetime
    b: Optional[str] = None


@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int


if __name__ == "__main__":
    bar = clifun.call(Bar)
    print(bar)
