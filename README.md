# clifun

Because cli's should be fun(ctions) ;).

```
import clifun

def my_program(a: int, b: str = "not provided"):
  print(f"Running some code with: a={a}, b={b}")

if __name__ == "__main__":
  clifun.call(my_program)
```

That's all it takes. Clifun will inspect your function and collect the values it needs it from command line arguments, environment variables, or config files, and then call it.

```
python examples/function --a 1
```
```
Running some code with: a=1, b=not provided
```

You can even run functions in any module without modifying the module at all

```
python clifun.py examples/module.py my_program --a 1
```

Or if you have environment variables defined

```
export A=1
export B=hi
python example.py
```
again yields without you having to provide values
```
Basic(a=1, b='hi')
```

`clifun` also supports nested objects (or functions taking complex objects as inputs)

```
from typing import Optional
import datetime as dt

import attr
import clifun


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: dt.datetime
    b: Optional[str] = None


@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int

def my_program(f: Foo, c: int):
    print(Bar(f, c))


if __name__ == "__main__":
    bar = clifun.call(my_program)
```

You specify values for the fields in the nested class by referring to them with a their field name in the outer class

```
python examples/advanced.py --c 1 --f.a 2020-01-01 --f.b hi
```
```
Bar(f=Foo(a=datetime.datetime(2021, 1, 1, 0, 0), b='hi'), c=1)
```

You can also supply one or more `json` formatted `config` files. Provide the name(s) of these files as positional arguments. `clifun` will search them, last file first, for any keys fields that are not provided at the command line before searching the environment.

```
python examples/advanced.py --c 1 examples/foo.json
```
```
Bar(f=Foo(a=datetime.datetime(2021, 1, 1, 0, 0), b='str'), c=1)
```

`clifun` is inspired by [clout](https://github.com/python-clout/clout), but I wanted to try being a bit more opinionated to make both the library and code using it simpler.


