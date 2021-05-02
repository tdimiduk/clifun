import attr
import datacli


@attr.s(auto_attribs=True, frozen=True)
class Basic:
    a: int
    b: str = "Optional"

def my_program(data: Foo):
    # Your actual program will go here. For this example we just print the input.
    print(data)


if __name__ == "__main__":
    foo = datacli.build(Foo)
    my_program(foo)
