from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, TypeAlias, Generic, Union, ParamSpec, Never, Any

from mafunca.curry import curry2, curry3, curry4


__all__ = [
    'Just',
    'Nothing',
    'Maybe',
    'just_of',
    'nothing_of',
    'from_null',
    'ap',
    'lift2',
    'lift3',
    'lift4',
    'lift',
]


T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True, slots=True, repr=True)
class Just(Generic[T]):
    """A container for non-nullable value"""
    value: T

    @property
    def is_just(self) -> bool:
        return True

    @property
    def is_nothing(self) -> bool:
        return False

    def map(self, fn: Callable[[T], R]) -> 'Just[R]':
        return Just(fn(self.value))

    def bind(self, fn: Callable[[T], 'Maybe[R]']) -> 'Maybe[R]':
        return fn(self.value)

    def get_or_else(self, alter: T) -> T:
        _ = alter  # a dummy operation for an unused argument
        return self.value

    def unfold(self, *, just: Callable[[T], R], nothing: Callable[[], R]) -> R:
        _ = nothing  # a dummy operation for an unused argument
        return just(self.value)


@dataclass(frozen=True, slots=True, repr=True)
class Nothing:
    """A container for nullable value"""

    @property
    def is_just(self) -> bool:
        return False

    @property
    def is_nothing(self) -> bool:
        return True

    def map(self, fn: Callable[[Never], R]) -> 'Nothing':
        _ = fn  # a dummy operation for an unused argument
        return self

    def bind(self, fn: Callable[[Never], 'Maybe[R]']) -> 'Nothing':
        _ = fn  # a dummy operation for an unused argument
        return self

    def get_or_else(self, alter: T) -> T:  # noqa
        return alter

    def unfold(self, *, just: Callable[[Never], R], nothing: Callable[[], R]) -> R:  # noqa
        return nothing()


Maybe: TypeAlias = Union[Just[T], Nothing]


def just_of(value: T) -> Just[T]:
    return Just(value)


def nothing_of() -> Nothing:
    return Nothing()


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_null(is_nullable: Callable[[R], bool] = lambda v: v is None) -> Callable[[R], Maybe[R]]:
    """Closure. Wraps a value in the Nothing if 'is_nullable' returns true, otherwise - Just"""
    def from_null_inner(value: R) -> Maybe[R]:
        return Nothing() if is_nullable(value) else Just(value)

    return from_null_inner


def ap(fn: Maybe[Callable[[T], R]], val: Maybe[T]) -> Maybe[R]:
    """
        Applies value enclosed in the Maybe to a function also in the Maybe.
    """
    if isinstance(fn, Nothing):
        return fn
    if isinstance(val, Nothing):
        return val
    return Just(fn.value(val.value))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2]
) -> Maybe[R]:
    """
        For a function with two POSITIONAL arguments.
        Wraps the passed function in the Maybe and applies the applicative method
    """
    return ap(ap(Just(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2],
        arg3: Maybe[A3]
) -> Maybe[R]:
    """
        For a function with three POSITIONAL arguments.
        Wraps the passed function in the Maybe and applies the applicative method
    """
    return ap(ap(ap(Just(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2],
        arg3: Maybe[A3],
        arg4: Maybe[A4],
) -> Maybe[R]:
    """
        For a function with four POSITIONAL arguments.
        Wraps the passed function in the Maybe and applies the applicative method
    """
    return ap(ap(ap(ap(Just(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: Maybe[Any]) -> Maybe[R]:
    unwrapped = list()
    for arg in args:
        if isinstance(arg, Nothing):
            return arg
        unwrapped.append(arg.value)
    return Just(fn(*unwrapped))
