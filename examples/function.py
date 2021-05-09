import clattr

def my_program(a: int, b: str = "not provided"):
    print(f"My program: a={a}, b={b}")
    return (a, b)

if __name__ == "__main__":
    clattr.run_function(my_program)
