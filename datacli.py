import argparse
import json
import os
from typing import Set, Type, TypeVar

import attr
import cattr


@attr.s(auto_attribs=True, frozen=True)
class Foo:
    a: int
    b: str


def make_parser(c: Type) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    for field in attr.fields(c):
        parser.add_argument(f"--{field.name}")
    return parser


def parse(c: Type) -> dict:
    return vars(make_parser(c).parse_args())


T = TypeVar("T")


def interpret_string(s: str, t: Type[T]) -> T:
    try:
        return cattr.structure(s, t)
    except:
        pass
    try:
        return cattr.structure(json.loads(s), t)
    except:
        raise Exception(f"Could not interpret {s} as type {t}")


def datacli(c: Type[T]) -> T:
    args = parse(c)
    missing: Set[str] = set()
    missing_type: Set[str] = set()
    for field in attr.fields(c):
        if field.type is None:
            missing_type.add(field.name)
        else:
            if args[field.name] is None:
                args[field.name] = os.environ.get(field.name, field.default)
            if args[field.name] == attr.NOTHING:
                missing.add(field.name)
            else:
                args[field.name] = interpret_string(args[field.name], field.type)

    if missing_type:
        raise Exception("All fields in cli class must have type signatures. Type signatures are missing for {missing_type}")

    if missing:
        raise Exception(f"Missing arguments: {missing}")

    return c(**args) #type: ignore


if __name__ == "__main__":
    print(datacli(Foo))
