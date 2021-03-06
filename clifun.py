import datetime as dt
import importlib.util
import inspect
import itertools
import json
import os
import pathlib
import sys
import types
import typing
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

S = TypeVar("S")
T = TypeVar("T")
O = TypeVar("O", Any, None)
StringInterpreters = Dict[Type[T], Callable[[str], T]]


def call(
    c: Callable[..., T],
    args: Optional[List[str]] = None,
    string_interpreters: Optional[StringInterpreters] = None,
) -> T:
    """
    Call a function from the command line

    Assembles the inputs to a function from command line arguments, environment variables, and config files and call it.
    """
    argv = sys.argv if args is None else args
    interpreters = (
        string_interpreters
        if string_interpreters is not None
        else default_string_interpreters()
    )
    annotated = annotate_callable(c, interpreters, [])
    provided_inputs = assemble_input_sources(argv)

    if provided_inputs.args.help:
        print_usage(annotated, header=True)
        sys.exit(0)

    needed_inputs = all_needed_inputs(annotated)

    unknown = invalid_args(provided_inputs.args.keyword.keys(), needed_inputs)
    if unknown:
        print(f"Unknown arguments: {unknown}")
        print_usage(annotated)
        sys.exit(1)

    resolved_inputs, missing_inputs = resolve_inputs(needed_inputs, provided_inputs)

    if missing_inputs:
        print(f"Missing arguments: {missing_inputs}")
        print_usage(annotated)
        sys.exit(1)

    return annotated(resolved_inputs)


################################################################################
# Interpreting strings into python types
################################################################################


def default_string_interpreters() -> StringInterpreters:
    return {
        int: int,
        float: float,
        str: str,
        bool: interpret_bool,
        dt.datetime: interpret_datetime,
        dt.date: interpret_date,
    }


class InterpretationError(ValueError):
    def __init__(self, s: str, t: T):
        self.s = s
        self.t = t

    def __str__(self):
        return f"Could not interpret '{self.s}' as {self.t}"


def interpret_bool(s: str) -> bool:
    """
    Slightly more intuitive bool iterpretation

    Raw python's `bool("false")==True` since it is a non-empty string
    """
    if s.lower() in {"t", "true", "yes", "y"}:
        return True
    elif s.lower() in {"f", "false", "no", "n"}:
        return False
    else:
        raise InterpretationError(s, bool)


def interpret_datetime(s: str) -> dt.datetime:
    """
    Date and time in isoformat
    """
    if hasattr(dt.datetime, "fromisoformat"):
        return dt.datetime.fromisoformat(s)
    else:
        # for python 3.6 where `fromisoformat` doesn't exist
        import isodate  # type: ignore

        return isodate.parse_datetime(s)


def interpret_date(s: str) -> dt.date:
    """
    Dates in YYYY-MM-DD format
    """
    return dt.date(*[int(i) for i in s.split("-")])


def interpret_string_as_type(
    s: str, t: Type[T], type_converters: StringInterpreters
) -> T:
    try:
        return (
            type_converters[unwrap_optional(t)](s)
            if is_optional(t)
            else type_converters[t](s)
        )
    except KeyError:
        raise InterpretationError(s, t)


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


Annotated = Union["AnnotatedParameter", "AnnotatedCallable"]


class AnnotatedCallable(Generic[T]):
    def __init__(
        self, callable: Callable[[...], T], name: str, needed_inputs: List[Annotated]
    ):
        self.callable = callable
        self.name = name
        self.needed_inputs = needed_inputs

    def __call__(self, inputs: Dict[str, str]):
        def collect(needed: Annotated):
            if isinstance(needed, AnnotatedParameter):
                value = inputs[needed.prefixed_name]
                if value is None:
                    if is_optional(needed.t):
                        return None
                    raise ValueError(
                        f"Somehow got None for non optional parameter {needed}"
                    )
                return needed(value)
            return needed(inputs)

        collected_inputs = {
            needed.name: collect(needed) for needed in self.needed_inputs
        }
        return self.callable(**collected_inputs)

    def __str__(self) -> str:
        return f"<callable: {self.name} {[str(i) for i in self.needed_inputs]}>"


class AnnotatedParameter(Generic[T]):
    def __init__(
        self, parameter: inspect.Parameter, from_string: Callable[[str], T], prefix
    ):
        self.parameter = parameter
        self.from_string = from_string
        self.prefix = prefix

    @property
    def name(self):
        return self.parameter.name

    @property
    def prefixed_name(self):
        return ".".join(self.prefix + [self.name])

    @property
    def t(self):
        return self.parameter.annotation

    @property
    def default(self):
        return self.parameter.default

    def __call__(self, input: Optional[str]) -> T:
        return self.from_string(input)

    def __str__(self) -> str:
        return f"<parameter: {self.name}: {self.t}>"


class InputSources:
    def __init__(self, args: Arguments, config_files: ConfigFiles):
        self.args = args
        self.config_files = config_files

    def get(self, key: str, default: Optional[T] = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default)
        return self.args.keyword.get(key, self.config_files.get(key, env_value))

    def get_value(self, value: AnnotatedParameter) -> Union[str, T, None]:
        return self.get(value.prefixed_name, value.default)


################################################################################
# Assemble inputs from the "outside world"
################################################################################


def assemble_input_sources(args: List[str]) -> InputSources:
    args_object = interpret_arguments(args)
    return InputSources(args_object, load_config_files(args_object.positional))


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


NOT_SPECIFIED = inspect._empty


def resolve_inputs(
    needed_inputs: List[AnnotatedParameter], provided_inputs: InputSources
) -> Tuple[Dict[str, Optional[str]], Set[str]]:
    missing = set()

    def resolve(v):
        s = provided_inputs.get_value(v)
        if s is None:
            if is_optional(v.t):
                return None
            else:
                missing.add(v.prefixed_name)
        if s == NOT_SPECIFIED:
            missing.add(v.prefixed_name)
        return s

    collected = {value.prefixed_name: resolve(value) for value in needed_inputs}

    return collected, missing


################################################################################
# Input validation and help
################################################################################


def check_usage(provided_inputs, needed_inputs) -> None:
    check_help(provided_inputs, needed_inputs)
    check_invalid_args(provided_inputs, needed_inputs)


def valid_args(values: List[AnnotatedParameter]) -> Set[str]:
    return {v.prefixed_name for v in values}


def invalid_args(args, allowed_args):
    return set(args) - valid_args(allowed_args)


def print_usage(annotated: AnnotatedCallable, header: bool = False) -> None:
    needed_inputs = all_needed_inputs(annotated)
    if header:
        print(f"{annotated.name}\n")
        doc = inspect.getdoc(annotated.callable)
        if doc:
            print(f"{doc}\n")
    print(f"Usage: {sys.argv[0]} [config_file] [--key: value]")
    print("\n".join(describe_needed(needed_inputs)))


def describe_needed(needed_inputs: List[AnnotatedParameter]) -> List[str]:
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


def all_needed_inputs(c: AnnotatedCallable) -> List[AnnotatedParameter]:
    def inner():
        for needed in c.needed_inputs:
            if isinstance(needed, AnnotatedParameter):
                yield needed
            else:
                yield from all_needed_inputs(needed)

    return list(inner())


def inspect_parameters(t: Type[T]) -> Iterable[inspect.Parameter]:
    return inspect.signature(t).parameters.values()


def is_optional(t: Type[T]) -> bool:
    return Union[t, None] == t


def unwrap_optional(t: Optional[Type[T]]) -> Type[T]:
    if hasattr(typing, "get_args"):
        args = typing.get_args(t)
        if len(args) == 0:
            return t
        else:
            return args[0]
    # fallback for python < 3.8. May be brittle since it depends on an `_`'d interface
    # this should use typing.get_args, but that is not available until python 3.8
    if type(t) != typing._GenericAlias:
        return t
    for s in t.__args__:  # type: ignore
        if s != type(None):
            return s


def type_to_string(t: Type[O]) -> str:
    if is_optional(t):
        return f"Optional[{unwrap_optional(t).__name__}]"
    return t.__name__


def annotate_parameter(
    parameter: inspect.Parameter, interpreter: StringInterpreters, prefix: List[str]
) -> Union[AnnotatedParameter, AnnotatedCallable]:
    if parameter.annotation == NOT_SPECIFIED:
        raise Exception(f"Missing type annotation for {parameter}")
    t = unwrap_optional(parameter.annotation)
    if t in interpreter:
        # We have found a "basic" value we know how to interpret
        return AnnotatedParameter(parameter, from_string=interpreter[t], prefix=prefix)

    # This is some kind of composite
    prefix = prefix + [parameter.name]
    return annotate_callable(parameter.annotation, interpreter, prefix, parameter.name)


def annotate_callable(
    callable: Callable[[...], T],
    interpreter: StringInterpreters,
    prefix: List[str],
    name: Optional[str] = None,
) -> AnnotatedCallable[T]:
    needed = [
        annotate_parameter(p, interpreter, prefix) for p in inspect_parameters(callable)
    ]
    return AnnotatedCallable(
        callable, name if name is not None else callable.__name__, needed
    )


################################################################################
# Make clifun.py usable as a script to call functions in any module
################################################################################


def import_module_by_path(path: pathlib.Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(target.name, str(target))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    print(sys.argv)
    if len(sys.argv) < 3:
        print("Usage: clifun.py path_to_module function_name ...")
        sys.exit(1)
    target = pathlib.Path(sys.argv[1]).resolve()
    function_name = sys.argv[2]
    arguments = sys.argv[2:]
    module = import_module_by_path(target)
    function = getattr(module, function_name)
    print(call(function, arguments))
