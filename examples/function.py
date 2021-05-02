import datacli

def my_program(a: int, b: str):
    print(f"My program: a={a}, b={b}")

if __name__ == "__main__":
    datacli.run_function(my_program)
