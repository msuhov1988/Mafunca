from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, TypeAlias, Generic, Union, ParamSpec, Never, Any

from mafunca.curry import curry2, curry3, curry4
from mafunca.common.exceptions import MonadError


__all__ = [
    'Ok',
    'Err',
    'Result',
    'ok_of',
    'err_of',
    'from_try',
    'ap',
    'lift2',
    'lift3',
    'lift4',
    'lift',
]


T = TypeVar("T")
E = TypeVar("E")
NewE = TypeVar('NewE')
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

    def map(self, fn: Callable[[T], R]) -> 'Ok[R]':
        return Ok(fn(self.value))

    def bind(self, fn: Callable[[T], 'Result[R, E]']) -> 'Result[R, E]':
        return fn(self.value)

    def map_error(self, fn: Callable[[Never], NewE]) -> 'Ok[T]':
        _ = fn  # a dummy operation for an unused argument
        return self

    def get_or_else(self, alter: T) -> T:
        _ = alter  # a dummy operation for an unused argument
        return self.value

    def unfold(self, *, ok: Callable[[T], R], err: Callable[[Never], R]) -> R:
        _ = err  # a dummy operation for an unused argument
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

    def map(self, fn: Callable[[Never], R]) -> 'Err[E]':
        _ = fn  # a dummy operation for an unused argument
        return self

    def bind(self, fn: Callable[[Never], 'Result[R, E]']) -> 'Err[E]':
        _ = fn  # a dummy operation for an unused argument
        return self

    def map_error(self, fn: Callable[[E], NewE]) -> 'Err[NewE]':
        return Err(fn(self.error))

    def get_or_else(self, alter: T) -> T:  # noqa
        return alter

    def unfold(self, *, ok: Callable[[Never], R], err: Callable[[E], R]) -> R:
        _ = ok  # a dummy operation for an unused argument
        return err(self.error)


Result: TypeAlias = Union[Ok[T], Err[E]]


def ok_of(value: T) -> Ok[T]:
    return Ok(value)


def err_of(error: E) -> Err[E]:
    return Err(error)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_try(fn: Callable[Args, R]) -> Callable[Args, Result[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'.
        'MonadError' is not suppressed.
    """

    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> Result[R, Exception]:
        try:
            return ok_of(fn(*args, **kwargs))
        except Exception as err:
            if isinstance(err, MonadError):
                raise err
            return Err(err)

    return wraps(fn)(from_try_inner)


def ap(fn: Result[Callable[[T], R], E], val: Result[T, E]) -> Result[R, E]:
    """
        Applies value enclosed in the Result to a function also in the Result.
    """
    if isinstance(fn, Err):
        return fn
    if isinstance(val, Err):
        return val
    return Ok(fn.value(val.value))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E]
) -> Result[R, E]:
    return ap(ap(Ok(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E],
        arg3: Result[A3, E]
) -> Result[R, E]:
    return ap(ap(ap(Ok(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E],
        arg3: Result[A3, E],
        arg4: Result[A4, E],
) -> Result[R, E]:
    return ap(ap(ap(ap(Ok(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: Result[Any, E]) -> Result[R, E]:
    unwrapped = list()
    for arg in args:
        if isinstance(arg, Err):
            return arg
        unwrapped.append(arg.value)
    return Ok(fn(*unwrapped))
