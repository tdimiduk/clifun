import argparse
import sys
import json
import os
from typing import Any, Set, Type, TypeVar, List, Optional, Dict, Union, Callable, Iterable, Generic
import typing
import collections
import pathlib
import inspect
import datetime as dt

import attr
from interpret_string import interpret as default_interpret, StringInterpreter

S = TypeVar("S")
T = TypeVar("T")
O = TypeVar("O", Any, None)

NotSpecified = inspect._empty

def is_optional(t: Type[T]) -> bool:
    return Union[t, None] == t


def unwrap_optional(t: Optional[Type[T]]) -> Type[T]:
    # this should use typing.get_args, but that is not available until python 3.8
    if type(t) != typing._GenericAlias:
        return t
    for s in t.__args__: # type: ignore
        if s != type(None):
            return s

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
            key = arg[2:]
            if arg in {"-h", "--help"}:
                return Arguments([], {}, True)
            if arg[:2] == "--":
                if len(args) < i+2:
                    raise ValueError(f"Missing value for argument: {key}")
                keyword[key] = args[i + 1]
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

    def get(self, key: str, default: Optional[T] = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default) if self.from_env else default
        return self.args.get(key, self.config_files.get(key, env_value))

    @classmethod
    def from_argv(cls, args: List[str] = sys.argv) -> "Source":
        args_object = Arguments.from_argv(args)
        return cls(args_object, load_config_files(args_object.positional))


def load_config_files(filenames: List[str]) -> ConfigFiles:
    # reverse the order so that later config files override earlier ones
    def load(name):
        if not pathlib.Path(name).exists():
            raise ValueError("Could not find config file {name}")
        return json.load(open(name))

    return ConfigFiles([load(name) for name in filenames[::-1]])


def find_obj(t: Type[T], source: Source, interpret: StringInterpreter, prefix: List[str] = []):
    if not attr.has(t):
        raise ValueError(f"{t} is not an attrs class")

    def find(field):
        if field.type is None:
            raise ValueError(f"Field {field.name} of {t} lacks a type annotation")
        return find_value(name=field.name, t=field.type, source=source, default=field.default, interpret=interpret, prefix=prefix)

    d: dict = {field.name: find(field) for field in attr.fields(t)}
    return t(**d)  # type: ignore


def find_value(name, t: Type[O], default, source: Source, interpret: StringInterpreter,  prefix: List[str] = []) -> O:
    prefix = prefix + [name]
    if attr.has(t):
        return find_obj(t=t, source=source, interpret=interpret, prefix=prefix)
    prefixed_name = ".".join(prefix)
    value = source.get(prefixed_name, default)

    if value in {attr.NOTHING, inspect._empty}:
        raise ValueError(f"could not find value for argument {prefixed_name} ({t}")
    if value is None and is_optional(t):
        return None
    return interpret.as_type(value, unwrap_optional(t))


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


def check_unused(arg_names: Iterable[str], t: Type[T]) -> Set[str]:
    return {arg for arg in arg_names if arg_unused(arg.split("."), t)}

def describe(t: Type[T]) -> Dict[str, Union[str, dict]]:
    def desc(t):
        if attr.has(t):
            return describe(t)
        if is_optional(t):
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

def build(t: Type[T], interpret=default_interpret) -> T:
    source = Source.from_argv()
    if source.args.help:
        print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
        print_argument_descriptions(describe(t))
        sys.exit(0)
    unknown = check_unused(source.args.keyword.keys(), t)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        sys.exit(1)
    return find_obj(t, source, interpret=interpret)


def run_function(c: Callable[...,T], interpret=default_interpret) -> T:
    source = Source.from_argv()
    def find(name: str, t: Type[T], default) -> T:
        if attr.has(t):
            return find_obj(t, source, interpret=interpret)
        else:
            return find_value(name, t, source=source, interpret=interpret, default=default)
    args_for_c = {
        name: find(name, parameter.annotation, parameter.default) for name, parameter in inspect.signature(c).parameters.items()
    }
    unused = set(sys.argv[1:])
    for name, value in args_for_c.items():
        if attr.has(value):
            unused = check_unused(unused, type(value))
        else:
            unused -= {name}

    return c(**args_for_c)

