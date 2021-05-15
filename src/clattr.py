import inspect
import json
import os
import pathlib
import sys
import typing
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

import attr

from interpret_string import StringInterpreter
from interpret_string import interpret as default_interpret
from tools import T, S, O, NOT_SPECIFIED, is_optional, unwrap_optional, type_to_string
import inputs


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
                if len(args) < i + 2:
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


def find_obj(
    t: Type[T],
    source: Source,
    interpret: StringInterpreter = default_interpret,
    prefix: List[str] = [],
):
    if not attr.has(t):
        raise ValueError(f"{t} is not an attrs class")

    def find(parameter):
        if parameter.annotation == NOT_SPECIFIED:
            raise ValueError(f"Field {parameter.name} of {t} lacks a type annotation")
        return find_value(
            name=parameter.name,
            t=parameter.annotation,
            source=source,
            default=parameter.default,
            interpret=interpret,
            prefix=prefix,
        )

    d: dict = {
        name: find(parameter)
        for name, parameter in inspect.signature(t).parameters.items()
    }
    return t(**d)  # type: ignore


def find_value(
    name,
    t: Type[O],
    default,
    source: Source,
    interpret: StringInterpreter,
    prefix: List[str] = [],
) -> O:
    prefix = prefix + [name]
    if attr.has(t):
        return find_obj(t=t, source=source, interpret=interpret, prefix=prefix)
    prefixed_name = ".".join(prefix)
    value = source.get(prefixed_name, default)

    if value == NOT_SPECIFIED:
        raise ValueError(f"could not find value for argument '{prefixed_name}' ({t}")
    if value is None and is_optional(t):
        return None
    return interpret.as_type(value, unwrap_optional(t))


def invalid_args(args, allowed_args):
    return set(args) - inputs.valid_args(allowed_args)

def check_invalid_args(source, input_values):
    unknown = invalid_args(source.args.keyword.keys(), input_values)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        print_usage(input_values)
        sys.exit(1)

def check_help(source, input_values):
    if source.args.help:
        print_usage(input_values)
        sys.exit(0)


def print_usage(input_values):
    print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
    print("\n".join(describe_needed(input_values)))

def describe_needed(input_values: List[inputs.Value]) -> List[str]:
    def desc(v):
        base = f" --{v.prefixed_name}: {type_to_string(v.t)}"
        if v.default != NOT_SPECIFIED:
            default = f'"{v.default}"' if isinstance(v.default, str) else v.default
            return f"{base} (default: {default})"
        return base
    return [desc(v) for v in input_values]

def build(t: Type[T], interpret=default_interpret) -> T:
    source = Source.from_argv()
    input_values = inputs.for_callable(t, interpret)
    check_help(source, input_values)
    check_invalid_args(source, input_values)
    return find_obj(t, source, interpret=interpret)


def run_function(
    c: Callable[..., T], interpret=default_interpret, args: List[str] = []
) -> T:
    source = Source.from_argv(args)
    input_values = inputs.for_callable(c, interpret)
    check_help(source, input_values)
    def find(name: str, t: Type[T], default) -> T:
        if attr.has(t):
            return find_obj(t, source, interpret=interpret)
        else:
            return find_value(
                name, t, source=source, interpret=interpret, default=default
            )

    args_for_c = {
        name: find(name, parameter.annotation, parameter.default)
        for name, parameter in inspect.signature(c).parameters.items()
    }
    check_invalid_args(source, input_values)

    return c(**args_for_c)
