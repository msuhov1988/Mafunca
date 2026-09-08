from collections.abc import Callable
from typing import TypeVar

from mafunca.maybe.build import Just, Nothing, Maybe


T = TypeVar("T")
R = TypeVar("R")


def fmap(maybe: Maybe[T], fn: Callable[[T], R]) -> Maybe[R]:
    if isinstance(maybe, Nothing):
        return maybe
    return Just(fn(maybe.value))


def bind(maybe: Maybe[T], fn: Callable[[T], Maybe[R]]) -> Maybe[R]:
    if isinstance(maybe, Nothing):
        return maybe
    return fn(maybe.value)


def fold(maybe: Maybe[T], on_just: Callable[[T], R], on_nothing: Callable[[], R]) -> R:
    if isinstance(maybe, Just):
        return on_just(maybe.value)
    return on_nothing()


def get_or_else(maybe: Maybe[T], default: T) -> T:
    if isinstance(maybe, Just):
        return maybe.value
    return default


def ap(maybe: Maybe[T], fn: Maybe[Callable[[T], R]]) -> Maybe[R]:
    """
        Applies value enclosed in the Result to a function also in the Result.
    """  
    if isinstance(fn, Nothing):
        return fn
    if isinstance(maybe, Nothing):
        return maybe    
    return Just(fn.value(maybe.value))
