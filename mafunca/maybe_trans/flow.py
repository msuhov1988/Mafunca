from collections.abc import Callable
from typing import TypeVar, cast

from mafunca.maybe_trans.build import MaybeResult
from mafunca.maybe.build import Just, Nothing, Maybe
from mafunca.result.build import Success, Fail, Result


T = TypeVar("T")
E = TypeVar("E")
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")


def fmap(fn: Callable[[T], R]) -> Callable[[MaybeResult[T, E]], MaybeResult[R, E]]:

    def fmap_inner(maybe_r: MaybeResult[T, E]) -> MaybeResult[R, E]:
        if isinstance(maybe_r, Nothing):
            return maybe_r
        result = maybe_r.value    
        if isinstance(result, Fail):
            return cast(MaybeResult[R, E], maybe_r)
        return Just(Success(fn(result.value)))

    return fmap_inner


def fmap_error(fn: Callable[[E1], E2]) -> Callable[[MaybeResult[T, E1]], MaybeResult[T, E2]]:

    def fmap_error_inner(maybe_r: MaybeResult[T, E1]) -> MaybeResult[T, E2]:
        if isinstance(maybe_r, Just):
            result = maybe_r.value
            if isinstance(result, Fail):
                return Just(Fail(fn(result.error)))
        return cast(MaybeResult[T, E2], maybe_r)

    return fmap_error_inner


def fmap_maybe(fn: Callable[[T], Maybe[R]]) -> Callable[[MaybeResult[T, E]], MaybeResult[R, E]]:

    def fmap_maybe_inner(maybe_r: MaybeResult[T, E]) -> MaybeResult[R, E]:
        if isinstance(maybe_r, Nothing):
            return maybe_r
        result = maybe_r.value    
        if isinstance(result, Fail):
            return cast(MaybeResult[R, E], maybe_r)
        maybe = fn(result.value)
        if isinstance(maybe, Nothing):
            return maybe
        return Just(Success(maybe.value))

    return fmap_maybe_inner


def fmap_result(fn: Callable[[T], Result[R, E]]) -> Callable[[MaybeResult[T, E]], MaybeResult[R, E]]:

    def fmap_result_inner(maybe_r: MaybeResult[T, E]) -> MaybeResult[R, E]:
        if isinstance(maybe_r, Nothing):
            return maybe_r
        result = maybe_r.value    
        if isinstance(result, Fail):
            return cast(MaybeResult[R, E], maybe_r)
        return Just(fn(result.value))   

    return fmap_result_inner


def bind(fn: Callable[[T], MaybeResult[R, E]]) -> Callable[[MaybeResult[T, E]], MaybeResult[R, E]]:

    def bind_inner(maybe_r: MaybeResult[T, E]) -> MaybeResult[R, E]:
        if isinstance(maybe_r, Nothing):
            return maybe_r
        result = maybe_r.value    
        if isinstance(result, Fail):
            return cast(MaybeResult[R, E], maybe_r)
        return fn(result.value)

    return bind_inner


def fold(on_just: Callable[[Result[T, E]], R], on_nothing: Callable[[], R]) -> Callable[[MaybeResult[T, E]], R]:

    def fold_inner(maybe_r: MaybeResult[T, E]) -> R:
        if isinstance(maybe_r, Nothing):
            return on_nothing()
        return on_just(maybe_r.value)

    return fold_inner


def get_or_else(default: T) -> Callable[[MaybeResult[T, E]], T]:

    def get_or_else_inner(maybe_r: MaybeResult[T, E]) -> T:
        if isinstance(maybe_r, Just) and isinstance(maybe_r.value, Success):
            return maybe_r.value.value
        return default

    return get_or_else_inner


def ap(maybe_r: MaybeResult[T, E]) -> Callable[[MaybeResult[Callable[[T], R], E]], MaybeResult[R, E]]:
    """
        Applies value enclosed in the container to a function also in the container.
    """
    def ap_inner(fn: MaybeResult[Callable[[T], R], E]) -> MaybeResult[R, E]: 
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

    return ap_inner
