from collections.abc import Callable
from typing import TypeVar, Any

from mafunca.result.build import Success, Fail, Result


R = TypeVar("R")
E = TypeVar("E")
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E]
) -> Result[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    if isinstance(arg2, Fail):
        return arg2
    return Success(fn(arg1.value, arg2.value))


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E],
        arg3: Result[A3, E]
) -> Result[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    if isinstance(arg2, Fail):
        return arg2
    if isinstance(arg3, Fail):
        return arg3
    return Success(fn(arg1.value, arg2.value, arg3.value))


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: Result[A1, E],
        arg2: Result[A2, E],
        arg3: Result[A3, E],
        arg4: Result[A4, E],
) -> Result[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    if isinstance(arg2, Fail):
        return arg2
    if isinstance(arg3, Fail):
        return arg3
    if isinstance(arg4, Fail):
        return arg4
    return Success(fn(arg1.value, arg2.value, arg3.value, arg4.value))


def lift(fn: Callable[..., R], *args: Result[Any, Any]) -> Result[R, Any]:
    unwrapped: list[Any] = list()
    for arg in args:
        if isinstance(arg, Fail):
            return arg
        unwrapped.append(arg.value)
    return Success(fn(*unwrapped))
