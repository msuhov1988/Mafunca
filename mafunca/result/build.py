from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, TypeAlias, TypeGuard, ParamSpec, Never


T_co = TypeVar("T_co", covariant=True)
E_co = TypeVar("E_co", covariant=True)
T = TypeVar("T")
R = TypeVar("R")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
Args = ParamSpec('Args')


@dataclass(frozen=True, slots=True, repr=True)
class Success(Generic[T_co]):
    """A container for a value representing a successful result"""
    value: T_co


@dataclass(frozen=True, slots=True, repr=True)
class Fail(Generic[E_co]):
    """A container for a value representing an error"""
    error: E_co


Result: TypeAlias = Success[T] | Fail[E]


def success(value: T) -> Result[T, Never]:
    return Success(value)


def fail(error: E) -> Result[Never, E]:
    return Fail(error)


def is_success(result: Result[T, E]) -> TypeGuard[Success[T]]:
    return True if isinstance(result, Success) else False


def is_fail(result: Result[T, E]) -> TypeGuard[Fail[E]]:
    return True if isinstance(result, Fail) else False


def from_try(fn: Callable[Args, R]) -> Callable[Args, Result[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'.
    """

    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> Result[R, Exception]:
        try:
            return Success(fn(*args, **kwargs))
        except Exception as err:
            return Fail(err)

    return wraps(fn)(from_try_inner)
