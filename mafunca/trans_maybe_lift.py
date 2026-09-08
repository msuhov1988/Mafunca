from collections.abc import Callable
from typing import TypeVar, cast, Any

from mafunca.trans_maybe import MaybeResult
from mafunca.maybe import Just, Nothing
from mafunca.result import Success, Fail


E = TypeVar("E")
R = TypeVar("R")
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: MaybeResult[A1, E],
        arg2: MaybeResult[A2, E]
) -> MaybeResult[R, E]:
    if isinstance(arg1, Nothing):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Fail):
        return cast(MaybeResult[R, E], arg1)
    
    if isinstance(arg2, Nothing):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Fail):
        return cast(MaybeResult[R, E], arg2)
    
    return Just(Success(fn(arg1_inner.value, arg2_inner.value)))


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: MaybeResult[A1, E],
        arg2: MaybeResult[A2, E],
        arg3: MaybeResult[A3, E]
) -> MaybeResult[R, E]:
    if isinstance(arg1, Nothing):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Fail):
        return cast(MaybeResult[R, E], arg1)
    
    if isinstance(arg2, Nothing):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Fail):
        return cast(MaybeResult[R, E], arg2)
    
    if isinstance(arg3, Nothing):
        return arg3
    arg3_inner = arg3.value
    if isinstance(arg3_inner, Fail):
        return cast(MaybeResult[R, E], arg3)
    
    return Just(Success(fn(arg1_inner.value, arg2_inner.value, arg3_inner.value)))


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: MaybeResult[A1, E],
        arg2: MaybeResult[A2, E],
        arg3: MaybeResult[A3, E],
        arg4: MaybeResult[A4, E],
) -> MaybeResult[R, E]:
    if isinstance(arg1, Nothing):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Fail):
        return cast(MaybeResult[R, E], arg1)
    
    if isinstance(arg2, Nothing):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Fail):
        return cast(MaybeResult[R, E], arg2)
    
    if isinstance(arg3, Nothing):
        return arg3
    arg3_inner = arg3.value
    if isinstance(arg3_inner, Fail):
        return cast(MaybeResult[R, E], arg3)

    if isinstance(arg4, Nothing):
        return arg4
    arg4_inner = arg4.value
    if isinstance(arg4_inner, Fail):
        return cast(MaybeResult[R, E], arg4)
    
    return Just(Success(fn(arg1_inner.value, arg2_inner.value, arg3_inner.value, arg4_inner.value)))


def lift(fn: Callable[..., R], *args: MaybeResult[Any, Any]) -> MaybeResult[R, Any]:
    unwrapped: list[Any] = list()
    for arg in args:
        if isinstance(arg, Nothing):
            return arg
        arg_inner = arg.value
        if isinstance(arg_inner, Fail):
            return arg
        unwrapped.append(arg_inner.value)
    return Just(Success(fn(*unwrapped)))
