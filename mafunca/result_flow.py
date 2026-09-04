from collections.abc import Callable
from typing import TypeVar

from mafunca.result import Success, Fail, Result


T = TypeVar("T")
R = TypeVar("R")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')


def fmap(fn: Callable[[T], R]) -> Callable[[Result[T, E]], Result[R, E]]:

    def fmap_inner(result: Result[T, E]) -> Result[R, E]:
        if isinstance(result, Fail):
            return result
        return Success(fn(result.value))

    return fmap_inner


def fmap_error(fn: Callable[[E1], E2]) -> Callable[[Result[T, E1]], Result[T, E2]]:

    def fmap_error_inner(result: Result[T, E1]) -> Result[T, E2]:
        if isinstance(result, Success):
            return result
        return Fail(fn(result.error))

    return fmap_error_inner


def bind(fn: Callable[[T], Result[R, E]]) -> Callable[[Result[T, E]], Result[R, E]]:

    def bind_inner(result: Result[T, E]) -> Result[R, E]:
        if isinstance(result, Fail):
            return result
        return fn(result.value)

    return bind_inner


def fold(on_success: Callable[[T], R], on_fail: Callable[[E], R]) -> Callable[[Result[T, E]], R]:

    def fold_inner(result: Result[T, E]) -> R:
        if isinstance(result, Success):
            return on_success(result.value)
        return on_fail(result.error)

    return fold_inner


def get_or_else(default: T) -> Callable[[Result[T, E]], T]:

    def get_or_else_inner(result: Result[T, E]) -> T:
        if isinstance(result, Success):
            return result.value
        return default

    return get_or_else_inner


def ap(result: Result[T, E]) -> Callable[[Result[Callable[[T], R], E]], Result[R, E]]:
    """
        Applies value enclosed in the Result to a function also in the Result.
    """
    def app_inner(fn: Result[Callable[[T], R], E]) -> Result[R, E]:
        if isinstance(result, Fail):
            return result 
        if isinstance(fn, Fail):
            return fn               
        return Success(fn.value(result.value))

    return app_inner
