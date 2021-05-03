# clattr

Simple specification of a command line interface with an attrs class or a function. 

You define the inputs to your program in the form of a (possibly nested) attrs class (dataclass). `clattr` will collect the fields of that class from command line arguments, environment variables and config files.

In the simplest form, let's consider a case where you are writing a program that wants two inputs of which one is optional

```
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
```

This could be invoked as
```
python examples/basic.py --a 1 --b hi
```
clattr will construct this object
```
Basic(a=1, b='hi')
```
Which you can then pass into the rest of your code as you please. The example simply prints it and then exits.

Or if you have environment variables defined

```
export A=1
export B=hi
python example.py
```
again yields
```
Basic(a=1, b='hi')
```

`clattr` also supports nested objects

```
from typing import Optional
import datetime as dt

import attr
import clattr


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: dt.datetime
    b: Optional[str] = None


@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int

def my_program(data: Bar):
    print(data)

if __name__ == "__main__":
    bar = clattr.build(Bar)
    my_program(bar)
```

You specify values for the fields in the nested class by referring to them with a their field name in the outer class

```
python examples/advanced.py --c 1 --f.a 1 --f.b hi
```
```
Bar(f=Foo(a=1, b='hi'), c=1)
```

You can also supply `json` one or more formatted `config` files. Provide the name(s) of these files as positional arguments. datacli will search them, last file first, for any keys fields that are not provided at the command line before searching the environment.

```
python examples/advanced.py --c 1 examples/foo.json
```
```
Bar(f=Foo(a=1, b='str'), c=1)
```

Inspired by [clout](https://github.com/python-clout/clout). `clout` appeared somewhat abandoned at the time I started `clattr`, and I wanted to try some things with treating type annotations as first class information to reduce boilerplate.


