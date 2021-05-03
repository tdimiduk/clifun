import attr
import clattr


@attr.s(auto_attribs=True, frozen=True)
class Basic:
    a: int
    b: str = "not provided"

def my_program(data: Basic):
    # Your actual program will go here. For this example we just print the input.
    print(data)


if __name__ == "__main__":
    data = clattr.build(Basic)
    my_program(data)
