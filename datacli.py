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


def unused(parts: List[str], t: Type[T]) -> bool:
    fields_dict = attr.fields_dict(t)
    if parts[0] not in fields_dict:
        return True
    elif len(parts) == 1:
        return False
    child_type = fields_dict[parts[0]].type
    if child_type is None:
        raise ValueError(f"Missing type annotation for field {child_type} of {t}")
    return unused(parts[1:], child_type)


def check_unused(args: Arguments, t: Type[T]) -> List[str]:

    return [arg for arg in args.keyword.keys() if unused(arg.split('.'), t)]



def clidata(t: Type[T]) -> T:
    args = Arguments.from_argv()
    unknown = check_unused(args, t)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        sys.exit(1)
    return find_obj(t, args)


