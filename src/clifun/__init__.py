from dataclasses import dataclass
import datetime as dt
import importlib.util
import inspect
import json
import os
import pathlib
import sys
import types
from typing import (
    Callable,
    Iterable,
    Set,
    TypeVar,
    Union,
    get_origin,
    get_args,
)

S = TypeVar("S")
T = TypeVar("T")
StringInterpreters = dict[type[T], Callable[[str], T]]


def call[T](
    c: Callable[..., T],
    args: list[str] | None = None,
    string_interpreters: StringInterpreters | None = None,
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


@dataclass
class InterpretationError[T](ValueError):
    s: str
    t: type[T]

    def __str__(self):
        return f"Could not interpret '{self.s}' as {self.t.__name__}"


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
    return dt.datetime.fromisoformat(s)


def interpret_date(s: str) -> dt.date:
    """
    Dates in YYYY-MM-DD format
    """
    return dt.date(*[int(i) for i in s.split("-")])


def interpret_string_as_type(
    s: str, t: type[T], type_converters: StringInterpreters
) -> T:
    try:
        return (
            type_converters[unwrap_optional(t)](s)
            if is_optional(t)
            else type_converters[t](s)
        )
    except KeyError:
        raise InterpretationError(s, t)


@dataclass
class Arguments:
    positional: list[str]
    keyword: dict[str, str]
    help: bool = False


@dataclass
class ConfigFiles:
    configs: list[dict[str, str]]

    def get(self, key: str, default: str | None = None) -> str | None:
        for config in self.configs:
            if key in config:
                return config[key]
        return default


Annotated = Union["AnnotatedParameter", "AnnotatedCallable"]


@dataclass
class AnnotatedCallable[T]:
    callable: Callable[[...], T]
    name: str
    needed_inputs: list[Annotated]

    def __call__(self, inputs: dict[str, str]):
        def collect(needed: Annotated):
            match needed:
                case AnnotatedParameter(t=t, prefixed_name=prefixed_name) as param:
                    value = inputs.get(prefixed_name)
                    if value is None:
                        if is_optional(t):
                            return None
                        else:
                            raise ValueError(f"Somehow got None for non optional parameter {param}")
                    return param(value)
                case AnnotatedCallable() as func:
                    return func(input)

        collected_inputs = {
            needed.name: collect(needed) for needed in self.needed_inputs
        }
        return self.callable(**collected_inputs)

    def __str__(self) -> str:
        return f"<callable: {self.name} {[str(i) for i in self.needed_inputs]}>"


@dataclass
class AnnotatedParameter[T]:
    parameter: inspect.Parameter
    from_string: Callable[[str], T]
    prefix: str

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

    def __call__(self, input: str | None) -> T:
        return self.from_string(input)

    def __str__(self) -> str:
        return f"<parameter: {self.name}: {self.t}>"


@dataclass
class InputSources:
    args: Arguments
    config_files: ConfigFiles

    def get(self, key: str, default: T | None = None) -> Union[str, T, None]:
        env_value = os.environ.get(key.upper(), default)
        return self.args.keyword.get(key, self.config_files.get(key, env_value))

    def get_value(self, value: AnnotatedParameter) -> Union[str, T, None]:
        return self.get(value.prefixed_name, value.default)


################################################################################
# Assemble inputs from the "outside world"
################################################################################


def assemble_input_sources(args: list[str]) -> InputSources:
    args_object = interpret_arguments(args)
    return InputSources(args_object, load_config_files(args_object.positional))


def interpret_arguments(args: list[str] | None = None) -> Arguments:
    if args is None:
        args = sys.argv

    args_iter = iter(args[1:])
    keyword = {}
    positional = []

    for arg in args_iter:
        if arg in {"-h", "--help"}:
            return Arguments([], {}, True)
        if arg.startswith("--"):
            key = arg[2:]
            try:
                value = next(args_iter)
                keyword[key] = value
            except StopIteration:
                raise ValueError(f"Missing value for argument: {key}")
        else:
             positional.append(arg)
    return Arguments(positional, keyword, False)


def load_config_files(filenames: list[str]) -> ConfigFiles:
    # reverse the order so that later config files override earlier ones
    def load(name):
        if not pathlib.Path(name).exists():
            raise ValueError(f"Could not find config file {name}")
        return json.load(open(name))

    return ConfigFiles([load(name) for name in filenames[::-1]])


NOT_SPECIFIED = inspect._empty


def resolve_inputs(
    needed_inputs: list[AnnotatedParameter], provided_inputs: InputSources
) -> tuple[dict[str, str | None], Set[str]]:
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


def valid_args(values: list[AnnotatedParameter]) -> Set[str]:
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


def describe_needed(needed_inputs: list[AnnotatedParameter]) -> list[str]:
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


def all_needed_inputs(c: AnnotatedCallable) -> list[AnnotatedParameter]:
    def inner():
        for needed in c.needed_inputs:
            if isinstance(needed, AnnotatedParameter):
                yield needed
            else:
                yield from all_needed_inputs(needed)

    return list(inner())


def inspect_parameters(t: type[T]) -> Iterable[inspect.Parameter]:
    return inspect.signature(t).parameters.values()


def is_optional(t: type[T]) -> bool:
    return get_origin(t) is types.UnionType and type(None) in get_args(t)

def unwrap_optional(t: type[T]) -> type[T]:
    if is_optional(t):
        return get_args(t)[0]
    return t


def type_to_string[T](t: type[T]) -> str:
    if is_optional(t):
        return f"Optional[{unwrap_optional(t).__name__}]"
    return t.__name__


def annotate_parameter(
    parameter: inspect.Parameter, interpreter: StringInterpreters, prefix: list[str]
) -> AnnotatedParameter | AnnotatedCallable:
    if parameter.annotation == inspect.Parameter.empty:
        raise TypeError(f"Missing type annotation for parameter '{parameter.name}'")
    unwrapped_type = unwrap_optional(parameter.annotation)

    if unwrapped_type in interpreter:
        # It's a primitive type we know how to handle
        return AnnotatedParameter(parameter, from_string=interpreter[unwrapped_type], prefix=prefix)

    # This is some kind of composite
    prefix = prefix + [parameter.name]
    return annotate_callable(parameter.annotation, interpreter, prefix, parameter.name)


def annotate_callable(
    callable: Callable[[...], T],
    interpreter: StringInterpreters,
    prefix: list[str],
    name: str | None = None,
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
