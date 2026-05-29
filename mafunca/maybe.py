from dataclasses import dataclass
from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar, TypeAlias, Generic, Union, ParamSpec, Any

from mafunca.specials import is_impure
from mafunca.curry import curry
from mafunca.common.exceptions import MonadError

__all__ = [
    'Just',
    'Nothing',
    'Maybe',
    'of',
    'from_null',
    'from_null_yield',
    'ap',
    'lift2',
    'lift3',
    'lift',
]


def _panic_on_impure(monad: str, method: str, *funcs: Callable) -> None:
    for fn in funcs:
        if is_impure(fn):
            raise MonadError(monad, method, f"impure function '{fn}' can not be used")


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

    def map(self, fn: Callable[[T], R]) -> 'Maybe[R]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        return Just(fn(self.value))

    def bind(self, fn: Callable[[T], 'Maybe[R]']) -> 'Maybe[R]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        return fn(self.value)

    def get_or_else(self, alter: T) -> T:  # noqa
        return self.value

    def unfold(self, *, just: Callable[[T], R], nothing: Callable[[], R]) -> R:
        """:raises MonadError: if the passed functions are marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', just, nothing)
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

    def map(self, fn: Callable[[T], R]) -> 'Maybe[R]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        return self

    def bind(self, fn: Callable[[T], 'Maybe[R]']) -> 'Maybe[R]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        return self

    def get_or_else(self, alter: T) -> T:  # noqa
        return alter

    def unfold(self, *, just: Callable[[T], R], nothing: Callable[[], R]) -> R:
        """:raises MonadError: if the passed functions are marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', just, nothing)
        return nothing()


Maybe: TypeAlias = Union[Just[T], Nothing]


def of(value: T) -> Just[T]:
    """Wraps a value in the container"""
    return Just(value)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")


def from_null(
        value: R,
        is_nullable: Callable[[R], bool] = lambda v: v is None
) -> Maybe[R]:
    """Wraps a value in the Nothing if 'is_nullable' returns true, otherwise - Just"""
    return Nothing() if is_nullable(value) else Just(value)


def from_null_yield(
        iterable: Iterable[R],
        is_nullable: Callable[[R], bool] = lambda v: v is None
) -> Iterator[Maybe[R]]:
    """
       Goes through the iterator, wraps values in the Nothing if 'is_nullable' returns true, otherwise - Just.
       Lazily returns values via yield.
    """
    for value in iterable:
        yield Nothing() if is_nullable(value) else Just(value)


def ap(fn: Maybe[Callable[[T], R]], val: Maybe[T]) -> Maybe[R]:
    """Applies value enclosed in the Maybe to a function also in the Maybe"""
    if fn.is_nothing:
        return fn
    if val.is_nothing:
        return val
    return Just(fn.value(val.value))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2]
) -> Maybe[R]:
    """Wraps the passed function in the Maybe and applies the applicative method"""
    return ap(
        ap(Just(lambda a: lambda b: fn(a, b)), arg1),
        arg2
    )


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2],
        arg3: Maybe[A3]
) -> Maybe[R]:
    """Wraps the passed function in the Maybe and applies the applicative method"""
    return ap(
        ap(
            ap(Just(lambda a: lambda b: lambda c: fn(a, b, c)), arg1),
            arg2
        ),
        arg3
    )


def lift(fn: Callable[..., R], *args: Maybe[Any]) -> Maybe[R]:
    """
       Wraps the passed function in the Maybe and applies the applicative method.
       Uses currying here.
    """
    result = Just(curry(fn))
    for arg in args:
        result = ap(result, arg)
    return result
