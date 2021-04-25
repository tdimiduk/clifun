import argparse
import sys
import json
import os
from typing import Set, Type, TypeVar, List, Optional, Dict
import collections

import attr
import cattr # type: ignore



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


@attr.s(auto_attribs=True, frozen=True)
class Arguments:
    positional: List[str]
    keyword: Dict[str, str]

    @classmethod
    def from_argv(cls, args: List[str] = sys.argv) -> "Arguments":
        i = 1
        keyword = {}
        positional = []
        while i < len(args):
            arg = args[i]
            if arg[:2] == '--':
                keyword[arg[2:]] = args[i+1]
                i += 2
            else:
                positional.append(arg)
                i += 1
        return cls(positional, keyword)

    def get(self, key: str) -> Optional[str]:
        return self.keyword.get(key)

def find_obj(t: Type[T], args: Arguments, prefix: List[str] = []):
    if not attr.has(t):
        raise ValueError(f"{t} is not an attrs class")
    def find(field):
        if field.type is None:
            raise ValueError(f"Field {field.name} of {t} lacks a type annotation")
        return find_value(field.name, field.type, args, prefix)
    d: dict = {field.name: find(field) for field in attr.fields(t)}
    return t(**d) # type: ignore


def find_value(name, t: Type[T], args: Arguments, prefix: List[str] = []) -> T:
    parts = prefix + [name]
    if attr.has(t):
        return find_obj(t, args, parts)
    prefixed_name = ".".join(parts)
    value = args.get(prefixed_name)
    if value is None:
        value = os.environ.get(prefixed_name)

    if value is None:
        raise ValueError(f"could not find value for argument {prefixed_name} ({t}")
    return interpret_string(value, t)


def clidata(t: Type[T]) -> T:
    return find_obj(t, Arguments.from_argv())


