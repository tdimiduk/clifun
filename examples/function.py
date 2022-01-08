import clifun


def my_program(a: int, b: str = "not provided"):
    "a simple program taking two options to demonstrate clifun"
    print(f"Running some code with: a={a}, b={b}")
    return (a, b)


if __name__ == "__main__":
    clifun.call(my_program)
