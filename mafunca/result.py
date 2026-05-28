from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, TypeAlias, Generic, Union, ParamSpec, Any

from mafunca.specials import is_impure
from mafunca.curry import curry
from mafunca.common.exceptions import MonadError

__all__ = [
    'Ok',
    'Err',
    'Result',
    'of',
    'from_try',
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
E = TypeVar("E")
R = TypeVar("R")


@dataclass(frozen=True, slots=True, repr=True)
class Ok(Generic[T]):
    """A container for a value representing a successful result"""
    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_error(self) -> bool:
        return False

    def map(self, fn: Callable[[T], R]) -> 'Result[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        return Ok(fn(self.value))

    def bind(self, fn: Callable[[T], 'Result[R, E]']) -> 'Result[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        return fn(self.value)

    def get_or_else(self, alter: T) -> T:  # noqa
        return self.value

    def unfold(self, *, ok: Callable[[T], R], err: Callable[[E], R]) -> R:
        """:raises MonadError: if the passed functions are marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', ok, err)
        return ok(self.value)


@dataclass(frozen=True, slots=True, repr=True)
class Err(Generic[E]):
    """A container for a value representing an error"""
    error: E

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_error(self) -> bool:
        return True

    def map(self, fn: Callable[[T], R]) -> 'Result[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        return self

    def bind(self, fn: Callable[[T], 'Result[R, E]']) -> 'Result[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        return self

    def get_or_else(self, alter: T) -> T:  # noqa
        return alter

    def unfold(self, *, ok: Callable[[T], R], err: Callable[[E], R]) -> R:
        """:raises MonadError: if the passed functions are marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', ok, err)
        return err(self.error)


Result: TypeAlias = Union[Ok[T], Err[E]]


def of(value: T) -> Ok[T]:
    """Wraps a value in the container"""
    return Ok(value)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
ExcSubtype = TypeVar('ExcSubtype', bound=Exception)


def from_try(fn: Callable[Args, R]) -> Callable[Args, Result[R, ExcSubtype]]:
    """Decorator. Performs a function, catching possible errors - heirs of 'Exception'"""

    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> Result[R, ExcSubtype]:
        try:
            return Ok(fn(*args, **kwargs))
        except Exception as err:
            return Err(err)

    return wraps(fn)(from_try_inner)


def ap(fn: Result[Callable[[T], R], E], val: Result[T, E]) -> Result[R, E]:
    """Applies value enclosed in the Result to a function also in the Result"""
    if fn.is_error:
        return fn
    if val.is_error:
        return val
    return Ok(fn.value(val.value))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E]
) -> Result[R, E]:
    """Wraps the passed function in the Result and applies the applicative method"""
    return ap(
        ap(Ok(lambda a: lambda b: fn(a, b)), arg1),
        arg2
    )


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E],
        arg3: Result[A3, E]
) -> Result[R, E]:
    """Wraps the passed function in the Result and applies the applicative method"""
    return ap(
        ap(
            ap(Ok(lambda a: lambda b: lambda c: fn(a, b, c)), arg1),
            arg2
        ),
        arg3
    )


def lift(fn: Callable[..., R], *args: Result[Any, E]) -> Result[R, E]:
    """
       Wraps the passed function in the Result and applies the applicative method.
       Uses currying here.
    """
    result = Ok(curry(fn))
    for arg in args:
        result = ap(result, arg)
    return result
