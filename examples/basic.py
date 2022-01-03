import attr

import clifun


@attr.s(auto_attribs=True, frozen=True)
class Basic:
    a: int
    b: str = "not provided"


def my_program(data: Basic):
    # Your actual program will go here. For this example we just print the input.
    print(data)


if __name__ == "__main__":
    data = clifun.call(Basic)
    my_program(data)
