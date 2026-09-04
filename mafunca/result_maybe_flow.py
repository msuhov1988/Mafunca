from collections.abc import Callable
from typing import TypeVar, cast

from mafunca.result_maybe import ResultMaybe
from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Success, Fail, Result


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")


def fmap(fn: Callable[[T], R]) -> Callable[[ResultMaybe[T, E]], ResultMaybe[R, E]]:

    def fmap_inner(result_m: ResultMaybe[T, E]) -> ResultMaybe[R, E]:
        if isinstance(result_m, Fail):
            return result_m
        maybe = result_m.value    
        if isinstance(maybe, Nothing):
            return cast(ResultMaybe[R, E], result_m)
        return Success(Just(fn(maybe.value)))

    return fmap_inner


def fmap_error(fn: Callable[[E1], E2]) -> Callable[[ResultMaybe[T, E1]], ResultMaybe[T, E2]]:

    def fmap_error_inner(result_m: ResultMaybe[T, E1]) -> ResultMaybe[T, E2]:
        if isinstance(result_m, Fail):
            return Fail(fn(result_m.error))
        return result_m

    return fmap_error_inner


def fmap_maybe(fn: Callable[[T], Maybe[R]]) -> Callable[[ResultMaybe[T, E]], ResultMaybe[R, E]]:

    def fmap_maybe_inner(result_m: ResultMaybe[T, E]) -> ResultMaybe[R, E]:
        if isinstance(result_m, Fail):
            return result_m
        maybe = result_m.value    
        if isinstance(maybe, Nothing):
            return cast(ResultMaybe[R, E], result_m)
        return Success(fn(maybe.value))

    return fmap_maybe_inner


def fmap_result(fn: Callable[[T], Result[R, E]]) -> Callable[[ResultMaybe[T, E]], ResultMaybe[R, E]]:

    def fmap_result_inner(result_m: ResultMaybe[T, E]) -> ResultMaybe[R, E]:
        if isinstance(result_m, Fail):
            return result_m
        maybe = result_m.value    
        if isinstance(maybe, Nothing):
            return cast(ResultMaybe[R, E], result_m)
        result = fn(maybe.value)
        if isinstance(result, Fail):
            return result
        return Success(Just(result.value))   

    return fmap_result_inner 


def bind(fn: Callable[[T], ResultMaybe[R, E]]) -> Callable[[ResultMaybe[T, E]], ResultMaybe[R, E]]:

    def bind_inner(result_m: ResultMaybe[T, E]) -> ResultMaybe[R, E]:
        if isinstance(result_m, Fail):
            return result_m
        maybe = result_m.value    
        if isinstance(maybe, Nothing):
            return cast(ResultMaybe[R, E], result_m)
        return fn(maybe.value)

    return bind_inner


def fold(on_success: Callable[[Maybe[T]], R], on_fail: Callable[[E], R]) -> Callable[[ResultMaybe[T, E]], R]:

    def fold_inner(result_m: ResultMaybe[T, E]) -> R:
        if isinstance(result_m, Fail):
            return on_fail(result_m.error)
        return on_success(result_m.value)

    return fold_inner


def get_or_else(default: T) -> Callable[[ResultMaybe[T, E]], T]: 

    def get_or_else_inner(result_m: ResultMaybe[T, E]) -> T:  
        if isinstance(result_m, Success) and isinstance(result_m.value, Just):
            return result_m.value.value
        return default

    return get_or_else_inner


def ap(result_m: ResultMaybe[T, E]) -> Callable[[ResultMaybe[Callable[[T], R], E]], ResultMaybe[R, E]]:
    """
        Applies value enclosed in the container to a function also in the container.
    """
    def ap_inner(fn: ResultMaybe[Callable[[T], R], E]) -> ResultMaybe[R, E]:   
        if isinstance(result_m, Fail):
            return result_m
        res_inner = result_m.value
        if isinstance(res_inner, Nothing):
            return cast(ResultMaybe[R, E], result_m)  
        if isinstance(fn, Fail):
            return fn
        fn_inner = fn.value
        if isinstance(fn_inner, Nothing):
            return cast(ResultMaybe[R, E], fn)     
        arg = res_inner.value
        func = fn_inner.value
        return Success(Just(func(arg)))

    return ap_inner