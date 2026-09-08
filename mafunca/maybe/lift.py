from collections.abc import Callable
from typing import TypeVar, Any

from mafunca.maybe.build import Just, Nothing, Maybe


R = TypeVar("R")
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2]
) -> Maybe[R]:
    if isinstance(arg1, Nothing):
        return arg1
    if isinstance(arg2, Nothing):
        return arg2
    return Just(fn(arg1.value, arg2.value))


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2],
        arg3: Maybe[A3]
) -> Maybe[R]:
    if isinstance(arg1, Nothing):
        return arg1
    if isinstance(arg2, Nothing):
        return arg2
    if isinstance(arg3, Nothing):
        return arg3
    return Just(fn(arg1.value, arg2.value, arg3.value))


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: Maybe[A1],
        arg2: Maybe[A2],
        arg3: Maybe[A3],
        arg4: Maybe[A4],
) -> Maybe[R]:
    if isinstance(arg1, Nothing):
        return arg1
    if isinstance(arg2, Nothing):
        return arg2
    if isinstance(arg3, Nothing):
        return arg3
    if isinstance(arg4, Nothing):
        return arg4
    return Just(fn(arg1.value, arg2.value, arg3.value, arg4.value))


def lift(fn: Callable[..., R], *args: Maybe[Any]) -> Maybe[R]:
    unwrapped: list[Any] = list()
    for arg in args:
        if isinstance(arg, Nothing):
            return arg
        unwrapped.append(arg.value)
    return Just(fn(*unwrapped))
