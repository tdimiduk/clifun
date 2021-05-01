import argparse
import sys
import json
import os
from typing import Set, Type, TypeVar, List, Optional, Dict, Union
import collections
import pathlib

import attr
import cattr  # type: ignore


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
    help: bool = False

    @classmethod
    def from_argv(cls, args: Optional[List[str]] = None) -> "Arguments":
        if args is None:
            args = sys.argv
        i = 1
        keyword = {}
        positional = []
        while i < len(args):
            arg = args[i]
            if arg in {"-h", "--help"}:
                return Arguments([], {}, True)
            if arg[:2] == "--":
                keyword[arg[2:]] = args[i + 1]
                i += 2
            else:
                positional.append(arg)
                i += 1
        return cls(positional, keyword, not (keyword or positional))

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.keyword.get(key, default)


@attr.s(auto_attribs=True, frozen=True)
class ConfigFiles:
    configs: List[Dict[str, str]]

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for config in self.configs:
            if key in config:
                return config[key]
        return default


@attr.s(auto_attribs=True, frozen=True)
class Source:
    args: Arguments
    config_files: ConfigFiles
    from_env: bool = True

    def get(self, key: str) -> Optional[str]:
        env_value = os.environ.get(key.upper()) if self.from_env else None
        return self.args.get(key, self.config_files.get(key, env_value))


def load_config_files(filenames: List[str]) -> ConfigFiles:
    # reverse the order so that later config files override earlier ones
    def load(name):
        if not pathlib.Path(name).exists():
            raise ValueError("Could not find config file {name}")
        return json.load(open(name))

    return ConfigFiles([load(name) for name in filenames[::-1]])


def find_obj(t: Type[T], source: Source, prefix: List[str] = []):
    if not attr.has(t):
        raise ValueError(f"{t} is not an attrs class")

    def find(field):
        if field.type is None:
            raise ValueError(f"Field {field.name} of {t} lacks a type annotation")
        return find_value(field.name, field.type, field.default, source, prefix)

    d: dict = {field.name: find(field) for field in attr.fields(t)}
    return t(**d)  # type: ignore


def find_value(name, t: Type[T], default, source: Source,  prefix: List[str] = []) -> T:
    prefix = prefix + [name]
    if attr.has(t):
        return find_obj(t, source, prefix)
    prefixed_name = ".".join(prefix)
    value = source.get(prefixed_name)
    if value is None:
        value = os.environ.get(prefixed_name, default)

    if value is None and default is not None:
        raise ValueError(f"could not find value for argument {prefixed_name} ({t}")
    return interpret_string(value, t)


def arg_unused(parts: List[str], t: Type[T]) -> bool:
    fields_dict = attr.fields_dict(t)
    if parts[0] not in fields_dict:
        return True
    elif len(parts) == 1:
        return False
    child_type = fields_dict[parts[0]].type
    if child_type is None:
        raise ValueError(f"Missing type annotation for field {child_type} of {t}")
    return arg_unused(parts[1:], child_type)


def check_unused(args: Arguments, t: Type[T]) -> List[str]:
    return [arg for arg in args.keyword.keys() if arg_unused(arg.split("."), t)]

def describe(t: Type[T]) -> Dict[str, Union[str, dict]]:
    def desc(t):
        if attr.has(t):
            return describe(t)
        # Python 3.6 compatable check for Optional
        if Union[t, None] == t:
            types = set(t.__args__) - {type(None)}
            types_str = ", ".join(t.__name__ for t in types)
            return f"Optional[{types_str}]"
        return str(t.__name__)
    return {f.name: desc(f.type) for f in attr.fields(t)}

def print_argument_descriptions(d: dict, prefix: List[str] = []) -> None:
    for key, value in d.items():
        namelist = prefix + [key]
        if isinstance(value, dict):
            print_argument_descriptions(value, namelist)
        else:
            name = ".".join(namelist)
            print(f" --{name}: {value}")

def clidata(t: Type[T], args: Optional[List[str]] = None) -> T:
    args = Arguments.from_argv(args)
    if args.help:
        print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
        print_argument_descriptions(describe(t))
        sys.exit(0)
    config_files = load_config_files(args.positional)
    unknown = check_unused(args, t)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        sys.exit(1)
    source = Source(args, config_files)
    return find_obj(t, source)
