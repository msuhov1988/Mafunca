from collections.abc import Callable
from typing import TypeVar, cast

from mafunca.trans_maybe import MaybeResult
from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Success, Fail, Result


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")


def fmap(maybe_r: MaybeResult[T, E], fn: Callable[[T], R]) -> MaybeResult[R, E]:
    if isinstance(maybe_r, Nothing):
        return maybe_r
    result = maybe_r.value    
    if isinstance(result, Fail):
        return cast(MaybeResult[R, E], maybe_r)
    return Just(Success(fn(result.value)))


def fmap_error(maybe_r: MaybeResult[T, E1], fn: Callable[[E1], E2]) -> MaybeResult[T, E2]:
    if isinstance(maybe_r, Just):
        result = maybe_r.value
        if isinstance(result, Fail):
            return Just(Fail(fn(result.error)))
    return cast(MaybeResult[T, E2], maybe_r)


def fmap_maybe(maybe_r: MaybeResult[T, E], fn: Callable[[T], Maybe[R]]) -> MaybeResult[R, E]:
    if isinstance(maybe_r, Nothing):
        return maybe_r
    result = maybe_r.value    
    if isinstance(result, Fail):
        return cast(MaybeResult[R, E], maybe_r)
    maybe = fn(result.value)
    if isinstance(maybe, Nothing):
        return maybe
    return Just(Success(maybe.value))


def fmap_result(maybe_r: MaybeResult[T, E], fn: Callable[[T], Result[R, E]]) -> MaybeResult[R, E]:
    if isinstance(maybe_r, Nothing):
        return maybe_r
    result = maybe_r.value    
    if isinstance(result, Fail):
        return cast(MaybeResult[R, E], maybe_r)
    return Just(fn(result.value))   


def bind(maybe_r: MaybeResult[T, E], fn: Callable[[T], MaybeResult[R, E]]) -> MaybeResult[R, E]:
    if isinstance(maybe_r, Nothing):
        return maybe_r
    result = maybe_r.value    
    if isinstance(result, Fail):
        return cast(MaybeResult[R, E], maybe_r)
    return fn(result.value)


def fold(maybe_r: MaybeResult[T, E], on_just: Callable[[Result[T, E]], R], on_nothing: Callable[[], R]) -> R:
    if isinstance(maybe_r, Nothing):
        return on_nothing()
    return on_just(maybe_r.value)


def get_or_else(maybe_r: MaybeResult[T, E], default: T) -> T:    
    if isinstance(maybe_r, Just) and isinstance(maybe_r.value, Success):
        return maybe_r.value.value
    return default


def ap(maybe_r: MaybeResult[T, E], fn: MaybeResult[Callable[[T], R], E]) -> MaybeResult[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
    """   
    if isinstance(fn, Nothing):
        return fn
    fn_inner = fn.value
    if isinstance(fn_inner, Fail):
        return cast(MaybeResult[R, E], fn)
    if isinstance(maybe_r, Nothing):
        return maybe_r
    res_inner = maybe_r.value
    if isinstance(res_inner, Fail):
        return cast(MaybeResult[R, E], maybe_r)           
    arg = res_inner.value
    func = fn_inner.value
    return Just(Success(func(arg)))
