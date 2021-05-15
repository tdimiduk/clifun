import attr
from typing import Any, List, Type, Generic, TypeVar, Callable, Iterator
import inspect
import itertools

from interpret_string import StringInterpreter
from tools import T, S, O, NOT_SPECIFIED, is_optional, unwrap_optional


@attr.s(auto_attribs=True, frozen=True)
class Value(Generic[O]):
    name: str
    t: Type[O]
    default: O
    prefix: List[str] = attr.Factory(list)

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


def for_parameter(parameter, interpret, prefix: List[str]) -> Iterator[Value]:
    if parameter.annotation == NOT_SPECIFIED:
        raise Exception(f"Missing type annotation for {parameter}")
    t = unwrap_optional(parameter.annotation)
    if t in interpret:
        return [Value.from_parameter(parameter, prefix=prefix)]
    prefix = prefix + [parameter.name]
    return itertools.chain(
        *(
            for_parameter(parameter, interpret, prefix)
            for parameter in inspect.signature(t).parameters.values()
        )
    )


def for_callable(c: Callable, interpret: StringInterpreter) -> List[Value]:
    return list(
        itertools.chain(
            *(
                for_parameter(parameter, interpret, [])
                for parameter in inspect.signature(c).parameters.values()
            )
        )
    )

