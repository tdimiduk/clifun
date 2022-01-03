import json
import os
import pathlib
import sys
import itertools
from typing import Any, Callable, Dict, List, Optional, Union
from typing import Callable, Generic, Iterable, List, Optional, Set, Type

from . import interpret_string
from .tools import (
    NOT_SPECIFIED,
    T,
    O,
    get_parameters,
    is_optional,
    type_to_string,
    unwrap_optional,
)


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
    provided_inputs = assemble_input_sources(argv)
    needed_inputs = inputs_for_callable(c, interpret)
    check_usage(provided_inputs, needed_inputs)
    return call_with_inputs(c, provided_inputs, needed_inputs, interpret)


################################################################################
# Data classes
#
# these should really be dataclasses, and will be converted when clifun drops compatability
# with python 3.6
################################################################################


class Arguments:
    def __init__(
        self, positional: List[str], keyword: Dict[str, str], help: bool = False
    ):
        self.positional = positional
        self.keyword = keyword
        self.help = help


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


class InputSources:
    def __init__(self, args: Arguments, config_files: ConfigFiles):
        self.args = args
        self.config_files = config_files

    def get(self, key: str, default: Optional[T] = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default)
        return self.args.get(key, self.config_files.get(key, env_value))

    def get_value(self, value: InputValue) -> Union[str, T, None]:
        return self.args.keyword.get(value.prefixed_name, value.default)


################################################################################
# Assemble inputs from the "outside world"
################################################################################


def call_with_inputs(
    c: Callable[..., T],
    provided_inputs: InputSources,
    needed_inputs: List[InputValue],
    interpret,
) -> T:
    return assemble(c, collect_values(needed_inputs, provided_inputs, interpret), [])


def assemble_input_sources(args: List[str]) -> InputSources:
    args_object = interpret_arguments(args)
    return InputSources(args_object, load_config_files(args_object.positional))


def assemble(c: Callable[..., T], collected_values: Dict[str, Any], prefix) -> T:
    def find(parameter):
        new_prefix = prefix + [parameter.name]
        prefixed_name = ".".join(new_prefix)
        if prefixed_name in collected_values:
            return collected_values[prefixed_name]
        return assemble(parameter.annotation, collected_values, new_prefix)

    d: dict = {parameter.name: find(parameter) for parameter in get_parameters(c)}
    return c(**d)


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


def load_config_files(filenames: List[str]) -> ConfigFiles:
    # reverse the order so that later config files override earlier ones
    def load(name):
        if not pathlib.Path(name).exists():
            raise ValueError(f"Could not find config file {name}")
        return json.load(open(name))

    return ConfigFiles([load(name) for name in filenames[::-1]])


def collect_values(
    values: List[InputValue],
    provided_inputs: InputSources,
    interpret: interpret_string.StringInterpreter,
) -> Dict[str, Any]:
    missing = set()

    def get(v):
        s = provided_inputs.get_value(v)
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


################################################################################
# Input validation and help
################################################################################


def check_usage(provided_inputs, needed_inputs) -> None:
    check_help(provided_inputs, needed_inputs)
    check_invalid_args(provided_inputs, needed_inputs)


def valid_args(values: List[InputValue]) -> Set[str]:
    return {v.prefixed_name for v in values}


def invalid_args(args, allowed_args):
    return set(args) - valid_args(allowed_args)


def check_invalid_args(provided_inputs, needed_inputs):
    unknown = invalid_args(provided_inputs.args.keyword.keys(), needed_inputs)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        print_usage(needed_inputs)
        raise ValueError(unknown)
        sys.exit(1)


def check_help(provided_inputs, needed_inputs):
    if provided_inputs.args.help:
        print_usage(needed_inputs)
        sys.exit(0)


def print_usage(needed_inputs):
    print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
    print("\n".join(describe_needed(needed_inputs)))


def describe_needed(needed_inputs: List[InputValue]) -> List[str]:
    def desc(v):
        base = f" --{v.prefixed_name}: {type_to_string(v.t)}"
        if v.default != NOT_SPECIFIED:
            default = f'"{v.default}"' if isinstance(v.default, str) else v.default
            return f"{base} (default: {default})"
        return base

    return [desc(v) for v in needed_inputs]


################################################################################
# Determine what inputs a function needs
################################################################################


def input_for_parameter(p, prefix=None) -> InputValue:
    if prefix is None:
        prefix = []
    return InputValue(name=p.name, t=p.annotation, default=p.default, prefix=prefix)


def inputs_for_parameter(
    parameter, interpret, prefix: List[str]
) -> Iterable[InputValue]:
    if parameter.annotation == NOT_SPECIFIED:
        raise Exception(f"Missing type annotation for {parameter}")
    t = unwrap_optional(parameter.annotation)
    if t in interpret:
        return [input_for_parameter(parameter, prefix=prefix)]
    prefix = prefix + [parameter.name]
    return itertools.chain(
        *(
            inputs_for_parameter(parameter, interpret, prefix)
            for parameter in get_parameters(t)
        )
    )


def inputs_for_callable(
    c: Callable, interpret: interpret_string.StringInterpreter
) -> List[InputValue]:
    return list(
        itertools.chain(
            *(
                inputs_for_parameter(parameter, interpret, [])
                for parameter in get_parameters(c)
            )
        )
    )
