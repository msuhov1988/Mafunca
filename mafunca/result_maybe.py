from collections.abc import Callable
from functools import wraps
from typing import TypeVar, TypeAlias, TypeGuard, ParamSpec, Never

from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Success, Fail, Result


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")
Args = ParamSpec('Args')


ResultMaybe: TypeAlias = Result[Maybe[T], E]


def just(value: T) -> ResultMaybe[T, Never]:
    return Success(Just(value))


def nothing() -> ResultMaybe[Never, Never]:
    return Success(Nothing())


def fail(error: E) -> ResultMaybe[Never, E]:
    return Fail(error)


def lift_maybe(maybe: Maybe[T]) -> ResultMaybe[T, Never]:
    return Success(maybe)


def lift_result(result: Result[T, E]) -> ResultMaybe[T, E]:
    if isinstance(result, Fail):
        return result
    return Success(Just(result.value))


def is_just(result_m: ResultMaybe[T, E]) -> TypeGuard[Success[Just[T]]]:    
    return isinstance(result_m, Success) and isinstance(result_m.value, Just)


def is_nothing(result_m: ResultMaybe[T, E]) -> TypeGuard[Success[Nothing]]:
    return isinstance(result_m, Success) and isinstance(result_m.value, Nothing)


def is_fail(result_m: ResultMaybe[T, E]) -> TypeGuard[Fail[E]]:
    return isinstance(result_m, Fail)


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> ResultMaybe[R, Never]:    
    return Success(Nothing() if is_nullable(value) else Just(value))


def from_try(fn: Callable[Args, R]) -> Callable[Args, ResultMaybe[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
    """  
    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> ResultMaybe[R, Exception]:
        try:
            return Success(Just(fn(*args, **kwargs)))
        except Exception as err:
            return Fail(err)

    return wraps(fn)(from_try_inner)


