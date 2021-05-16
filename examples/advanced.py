from typing import Optional
import datetime as dt

import attr
import clattr


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: dt.datetime
    b: Optional[str] = None


@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int


def my_program(data: Bar):
    print(data)


if __name__ == "__main__":
    bar = clattr.call(Bar)
    my_program(bar)
