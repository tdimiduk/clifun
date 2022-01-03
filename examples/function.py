import clifun


def my_program(a: int, b: str = "not provided"):
    print(f"Running some code with: a={a}, b={b}")
    return (a, b)


if __name__ == "__main__":
    clifun.call(my_program)
