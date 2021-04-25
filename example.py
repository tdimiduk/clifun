import attr
import datacli


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: int
    b: str


@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int


if __name__ == "__main__":
    print(datacli.clidata(Bar))
