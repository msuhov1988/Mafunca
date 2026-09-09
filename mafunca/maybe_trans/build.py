from collections.abc import Callable
from functools import wraps
from typing import TypeVar, TypeAlias, TypeGuard, ParamSpec, Never

from mafunca.maybe.build import Just, Nothing, Maybe
from mafunca.result.build import Success, Fail, Result


__all__ = [
    "MaybeResult",
    "just",
    "nothing",
    "fail",
    "lift_maybe",
    "lift_result",
    "is_just",
    "is_nothing",
    "is_fail",
    "from_null",
    "from_try",
]


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")
Args = ParamSpec('Args')


MaybeResult: TypeAlias = Maybe[Result[T, E]]


def just(value: T) -> MaybeResult[T, Never]:
    return Just(Success(value))


def nothing() -> MaybeResult[Never, Never]:
    return Nothing()


def fail(error: E) -> MaybeResult[Never, E]:
    return Just(Fail(error))


def lift_maybe(maybe: Maybe[T]) -> MaybeResult[T, Never]:
    if isinstance(maybe, Nothing):
        return maybe
    return Just(Success(maybe.value))


def lift_result(result: Result[T, E]) -> MaybeResult[T, E]:    
    return Just(result)


def is_just(maybe_r: MaybeResult[T, E]) -> TypeGuard[Just[Success[T]]]:    
    return isinstance(maybe_r, Just) and isinstance(maybe_r.value, Success)


def is_nothing(maybe_r: MaybeResult[T, E]) -> TypeGuard[Nothing]:
    return isinstance(maybe_r, Nothing)


def is_fail(maybe_r: MaybeResult[T, E]) -> TypeGuard[Just[Fail[E]]]:
    return isinstance(maybe_r, Just) and isinstance(maybe_r.value, Fail)


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> MaybeResult[R, Never]:    
    return Nothing() if is_nullable(value) else Just(Success(value))


def from_try(fn: Callable[Args, R]) -> Callable[Args, MaybeResult[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
    """  
    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> MaybeResult[R, Exception]:
        try:
            return Just(Success(fn(*args, **kwargs)))
        except Exception as err:
            return Just(Fail(err))

    return wraps(fn)(from_try_inner)