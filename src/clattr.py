import json
import os
import pathlib
import sys
from typing import Any, Callable, Dict, List, Optional, Union

import inputs
from interpret_string import StringInterpreter
from interpret_string import interpret as default_interpret
from tools import NOT_SPECIFIED, T, get_parameters, is_optional, type_to_string


class Arguments:
    def __init__(
        self, positional: List[str], keyword: Dict[str, str], help: bool = False
    ):
        self.positional = positional
        self.keyword = keyword
        self.help = help

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


class ConfigFiles:
    def __init__(self, configs: List[Dict[str, str]]):
        self.configs = configs

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for config in self.configs:
            if key in config:
                return config[key]
        return default


class Source:
    def __init__(
        self, args: Arguments, config_files: ConfigFiles, from_env: bool = True
    ):
        self.args = args
        self.config_files = config_files
        self.from_env = from_env

    def get(self, key: str, default: Optional[T] = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default) if self.from_env else default
        return self.args.get(key, self.config_files.get(key, env_value))

    def get_value(self, value: inputs.Value) -> Union[str, T, None]:
        return self.get(value.prefixed_name, value.default)

    @classmethod
    def from_argv(cls, args: List[str] = sys.argv) -> "Source":
        args_object = Arguments.from_argv(args)
        return cls(args_object, load_config_files(args_object.positional))


def load_config_files(filenames: List[str]) -> ConfigFiles:
    # reverse the order so that later config files override earlier ones
    def load(name):
        if not pathlib.Path(name).exists():
            raise ValueError(f"Could not find config file {name}")
        return json.load(open(name))

    return ConfigFiles([load(name) for name in filenames[::-1]])


def assemble(c: Callable[..., T], collected_values: Dict[str, Any], prefix) -> T:
    def find(parameter):
        new_prefix = prefix + [parameter.name]
        prefixed_name = ".".join(new_prefix)
        if prefixed_name in collected_values:
            return collected_values[prefixed_name]
        return assemble(parameter.annotation, collected_values, new_prefix)

    d: dict = {parameter.name: find(parameter) for parameter in get_parameters(c)}
    return c(**d)


def collect_values(
    values: List[inputs.Value], source: Source, interpret: StringInterpreter
) -> Dict[str, Any]:
    missing = set()

    def get(v):
        s = source.get_value(v)
        if s is None:
            if is_optional(v.t):
                return None
            else:
                raise ValueError(
                    f"Got None for non Optional parameter {v.prefixed_name} of type {v.t}"
                )

        if s == NOT_SPECIFIED:
            missing.add(v.prefixed_name)
            return s
        return interpret.as_type(s, v.t)

    collected = {value.prefixed_name: get(value) for value in values}
    if missing:
        raise ValueError(f"Missing arguments: {missing}")
    return collected


def invalid_args(args, allowed_args):
    return set(args) - inputs.valid_args(allowed_args)


def check_invalid_args(source, input_values):
    unknown = invalid_args(source.args.keyword.keys(), input_values)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        print_usage(input_values)
        raise ValueError(unknown)
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


def call(
    c: Callable[..., T], args: Optional[List[str]] = None, interpret=default_interpret
) -> T:
    argv = sys.argv if args is None else args
    source = Source.from_argv(argv)
    input_values = inputs.for_callable(c, interpret)
    check_help(source, input_values)
    check_invalid_args(source, input_values)
    return assemble(c, collect_values(input_values, source, interpret), [])
