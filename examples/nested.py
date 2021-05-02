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

def my_program(data: Bar):
    print(data)

if __name__ == "__main__":
    bar = datacli.build(Bar)
    my_program(bar)
