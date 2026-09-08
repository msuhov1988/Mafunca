from collections.abc import Callable
from typing import TypeVar

from mafunca.result import Success, Fail, Result


T = TypeVar("T")
R = TypeVar("R")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')


def fmap(result: Result[T, E], fn: Callable[[T], R]) -> Result[R, E]:
    if isinstance(result, Fail):
        return result
    return Success(fn(result.value))


def fmap_error(result: Result[T, E1], fn: Callable[[E1], E2]) -> Result[T, E2]:
    if isinstance(result, Success):
        return result
    return Fail(fn(result.error))


def bind(result: Result[T, E], fn: Callable[[T], Result[R, E]]) -> Result[R, E]:
    if isinstance(result, Fail):
        return result
    return fn(result.value)


def fold(result: Result[T, E], on_success: Callable[[T], R], on_fail: Callable[[E], R]) -> R:
    if isinstance(result, Success):
        return on_success(result.value)
    return on_fail(result.error)


def get_or_else(result: Result[T, E], default: T) -> T:
    if isinstance(result, Success):
        return result.value
    return default


def ap(result: Result[T, E], fn: Result[Callable[[T], R], E]) -> Result[R, E]:
    """
        Applies value enclosed in the Result to a function also in the Result.
    """
    if isinstance(fn, Fail):
        return fn 
    if isinstance(result, Fail):
        return result           
    return Success(fn.value(result.value))
