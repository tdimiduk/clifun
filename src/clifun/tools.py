import inspect
import typing
from typing import Any, Iterable, Optional, Type, TypeVar, Union

S = TypeVar("S")
T = TypeVar("T")
O = TypeVar("O", Any, None)

NOT_SPECIFIED = inspect._empty


def get_parameters(t: Type[T]) -> Iterable[inspect.Parameter]:
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
