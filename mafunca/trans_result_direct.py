from collections.abc import Callable
from typing import TypeVar, cast

from mafunca.trans_result import ResultMaybe
from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Success, Fail, Result


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")


def fmap(result_m: ResultMaybe[T, E], fn: Callable[[T], R]) -> ResultMaybe[R, E]:
    if isinstance(result_m, Fail):
        return result_m
    maybe = result_m.value    
    if isinstance(maybe, Nothing):
        return cast(ResultMaybe[R, E], result_m)
    return Success(Just(fn(maybe.value)))


def fmap_error(result_m: ResultMaybe[T, E1], fn: Callable[[E1], E2]) -> ResultMaybe[T, E2]:
    if isinstance(result_m, Fail):
        return Fail(fn(result_m.error))
    return result_m


def fmap_maybe(result_m: ResultMaybe[T, E], fn: Callable[[T], Maybe[R]]) -> ResultMaybe[R, E]:
    if isinstance(result_m, Fail):
        return result_m
    maybe = result_m.value    
    if isinstance(maybe, Nothing):
        return cast(ResultMaybe[R, E], result_m)
    return Success(fn(maybe.value))


def fmap_result(result_m: ResultMaybe[T, E], fn: Callable[[T], Result[R, E]]) -> ResultMaybe[R, E]:
    if isinstance(result_m, Fail):
        return result_m
    maybe = result_m.value    
    if isinstance(maybe, Nothing):
        return cast(ResultMaybe[R, E], result_m)
    result = fn(maybe.value)
    if isinstance(result, Fail):
        return result
    return Success(Just(result.value))    


def bind(result_m: ResultMaybe[T, E], fn: Callable[[T], ResultMaybe[R, E]]) -> ResultMaybe[R, E]:
    if isinstance(result_m, Fail):
        return result_m
    maybe = result_m.value    
    if isinstance(maybe, Nothing):
        return cast(ResultMaybe[R, E], result_m)
    return fn(maybe.value)


def fold(result_m: ResultMaybe[T, E], on_success: Callable[[Maybe[T]], R], on_fail: Callable[[E], R]) -> R:
    if isinstance(result_m, Fail):
        return on_fail(result_m.error)
    return on_success(result_m.value)


def get_or_else(result_m: ResultMaybe[T, E], default: T) -> T:    
    if isinstance(result_m, Success) and isinstance(result_m.value, Just):
        return result_m.value.value
    return default


def ap(result_m: ResultMaybe[T, E], fn: ResultMaybe[Callable[[T], R], E]) -> ResultMaybe[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
    """   
    if isinstance(fn, Fail):
        return fn
    fn_inner = fn.value
    if isinstance(fn_inner, Nothing):
        return cast(ResultMaybe[R, E], fn) 
    if isinstance(result_m, Fail):
        return result_m
    res_inner = result_m.value
    if isinstance(res_inner, Nothing):
        return cast(ResultMaybe[R, E], result_m)         
    arg = res_inner.value
    func = fn_inner.value
    return Success(Just(func(arg)))
