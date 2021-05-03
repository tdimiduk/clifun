# clattr

Simple specification of a command line interface with an attrs class or a function.

You define the inputs to your program in the form of a (possibly nested) attrs class (dataclass). `clattr` will collect the fields of that class from command line arguments, environment variables and config files.

In the simplest form, let's consider a case where you are writing a program that wants two inputs

```
@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: int
    b: str
```

This could be invoked as
```
python example.py --a 1 --b hi
```
datacli will construct this object
```
Foo(a=1, b='hi')
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
Foo(a=1, b='hi')
```

`datacli` also supports nested objects

```
@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: int
    b: str

@attr.s(auto_attribs=True, frozen=True)
class Bar:
    f: Foo
    c: int
```

You specify values for the fields in the nested class by referring to them with a their field name in the outer class

```
python example-nested.py --c 1 --f.a 1 --f.b hi
```
```
Bar(f=Foo(a=1, b='hi'), c=1)
```

You can also supply `json` one or more formatted `config` files. Provide the name(s) of these files as positional arguments. datacli will search them, last file first, for any keys fields that are not provided at the command line before searching the environment.

```
python example-nested.py --c 1 foo.json
```
```
Bar(f=Foo(a=1, b='str'), c=1)
```

Inspired by [clout](https://github.com/python-clout/clout) but I wrote a new library because that one hasn't been updated in a year and I wanted to make some different choices and be opinionated to offer a simple out of the box experience.

