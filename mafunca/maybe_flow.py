from collections.abc import Callable
from typing import TypeVar

from mafunca.maybe import Just, Nothing, Maybe


T = TypeVar("T")
R = TypeVar("R")


def fmap(fn: Callable[[T], R]) -> Callable[[Maybe[T]], Maybe[R]]:

    def fmap_inner(maybe: Maybe[T]) -> Maybe[R]:
        if isinstance(maybe, Nothing):
            return maybe
        return Just(fn(maybe.value))

    return fmap_inner


def bind(fn: Callable[[T], Maybe[R]]) -> Callable[[Maybe[T]], Maybe[R]]:

    def bind_inner(maybe: Maybe[T]) -> Maybe[R]:
        if isinstance(maybe, Nothing):
            return maybe
        return fn(maybe.value)

    return bind_inner


def fold(on_just: Callable[[T], R], on_nothing: Callable[[], R]) -> Callable[[Maybe[T]], R]:

    def fold_inner(maybe: Maybe[T]) -> R:
        if isinstance(maybe, Just):
            return on_just(maybe.value)
        return on_nothing()

    return fold_inner


def get_or_else(default: T) -> Callable[[Maybe[T]], T]:

    def get_or_else_inner(maybe: Maybe[T]) -> T:
        if isinstance(maybe, Just):
            return maybe.value
        return default

    return get_or_else_inner


def ap(maybe: Maybe[T]) -> Callable[[Maybe[Callable[[T], R]]], Maybe[R]]:
    """
        Applies value enclosed in the Maybe to a function also in the Maybe.
    """
    def ap_inner(fn: Maybe[Callable[[T], R]]) -> Maybe[R]:        
        if isinstance(maybe, Nothing):
            return maybe
        if isinstance(fn, Nothing):
            return fn
        return Just(fn.value(maybe.value))

    return ap_inner
