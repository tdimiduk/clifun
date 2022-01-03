import json
import os
import pathlib
import sys
import itertools
from typing import Any, Callable, Dict, List, Optional, Union
from typing import Callable, Generic, Iterable, List, Optional, Set, Type

from . import interpret_string
from .tools import NOT_SPECIFIED, T, O, get_parameters, is_optional, type_to_string, unwrap_optional


def call(
    c: Callable[..., T],
    args: Optional[List[str]] = None,
    interpret=interpret_string.interpret,
) -> T:
    """
    Call a function from the command line

    Assembles the inputs to a function from command line arguments, environment variables, and config files and call it.
    """
    argv = sys.argv if args is None else args
    all_inputs = assemble_input_sources(argv)
    input_values = inputs_for_callable(c, interpret)
    check_help(all_inputs, input_values)
    check_invalid_args(all_inputs, input_values)
    return assemble(c, collect_values(input_values, all_inputs, interpret), [])


class Arguments:
    def __init__(
        self, positional: List[str], keyword: Dict[str, str], help: bool = False
    ):
        self.positional = positional
        self.keyword = keyword
        self.help = help

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.keyword.get(key, default)


def interpret_arguments(args: Optional[List[str]] = None) -> Arguments:
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
    return Arguments(positional, keyword, not (keyword or positional))


class ConfigFiles:
    def __init__(self, configs: List[Dict[str, str]]):
        self.configs = configs

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for config in self.configs:
            if key in config:
                return config[key]
        return default

class InputValue(Generic[O]):
    def __init__(
        self, name: str, t: Type[O], default: O, prefix: Optional[List[str]] = None
    ):
        self.name = name
        self.t = t
        self.default = default
        self.prefix = [] if prefix is None else prefix

    @property
    def prefixed_name(self):
        return ".".join(self.prefix + [self.name])

    @classmethod
    def from_parameter(cls, p, prefix=None):
        if prefix is None:
            prefix = []
        return cls(
            name=p.name,
            t=p.annotation,
            default=p.default,
            prefix=prefix,
        )

class InputSources:
    def __init__(self, args: Arguments, config_files: ConfigFiles):
        self.args = args
        self.config_files = config_files

    def get(self, key: str, default: Optional[T] = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default)
        return self.args.get(key, self.config_files.get(key, env_value))

    def get_value(self, value: InputValue) -> Union[str, T, None]:
        return self.get(value.prefixed_name, value.default)


def assemble_input_sources(args: List[str]) -> InputSources:
    args_object = interpret_arguments(args)
    return InputSources(args_object, load_config_files(args_object.positional))


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
    values: List[InputValue],
    all_inputs: InputSources,
    interpret: interpret_string.StringInterpreter,
) -> Dict[str, Any]:
    missing = set()

    def get(v):
        s = all_inputs.get_value(v)
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
    return set(args) - valid_args(allowed_args)


def check_invalid_args(all_inputs, input_values):
    unknown = invalid_args(all_inputs.args.keyword.keys(), input_values)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        print_usage(input_values)
        raise ValueError(unknown)
        sys.exit(1)


def check_help(all_inputs, input_values):
    if all_inputs.args.help:
        print_usage(input_values)
        sys.exit(0)


def print_usage(input_values):
    print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
    print("\n".join(describe_needed(input_values)))


def describe_needed(input_values: List[InputValue]) -> List[str]:
    def desc(v):
        base = f" --{v.prefixed_name}: {type_to_string(v.t)}"
        if v.default != NOT_SPECIFIED:
            default = f'"{v.default}"' if isinstance(v.default, str) else v.default
            return f"{base} (default: {default})"
        return base

    return [desc(v) for v in input_values]



def inputs_for_parameter(parameter, interpret, prefix: List[str]) -> Iterable[InputValue]:
    if parameter.annotation == NOT_SPECIFIED:
        raise Exception(f"Missing type annotation for {parameter}")
    t = unwrap_optional(parameter.annotation)
    if t in interpret:
        return [InputValue.from_parameter(parameter, prefix=prefix)]
    prefix = prefix + [parameter.name]
    return itertools.chain(
        *(
            inputs_for_parameter(parameter, interpret, prefix)
            for parameter in get_parameters(t)
        )
    )


def inputs_for_callable(c: Callable, interpret: interpret_string.StringInterpreter) -> List[InputValue]:
    return list(
        itertools.chain(
            *(
                inputs_for_parameter(parameter, interpret, [])
                for parameter in get_parameters(c)
            )
        )
    )


def valid_args(values: List[InputValue]) -> Set[str]:
    return {v.prefixed_name for v in values}
