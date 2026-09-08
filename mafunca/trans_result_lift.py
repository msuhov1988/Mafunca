from collections.abc import Callable
from typing import TypeVar, cast, Any

from mafunca.trans_result import ResultMaybe
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
        arg1: ResultMaybe[A1, E],
        arg2: ResultMaybe[A2, E]
) -> ResultMaybe[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Nothing):
        return cast(ResultMaybe[R, E], arg1)
    
    if isinstance(arg2, Fail):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Nothing):
        return cast(ResultMaybe[R, E], arg2)
    
    return Success(Just(fn(arg1_inner.value, arg2_inner.value)))


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: ResultMaybe[A1, E],
        arg2: ResultMaybe[A2, E],
        arg3: ResultMaybe[A3, E]
) -> ResultMaybe[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Nothing):
        return cast(ResultMaybe[R, E], arg1)
    
    if isinstance(arg2, Fail):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Nothing):
        return cast(ResultMaybe[R, E], arg2)
    
    if isinstance(arg3, Fail):
        return arg3
    arg3_inner = arg3.value
    if isinstance(arg3_inner, Nothing):
        return cast(ResultMaybe[R, E], arg3)
    
    return Success(Just(fn(arg1_inner.value, arg2_inner.value, arg3_inner.value)))


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: ResultMaybe[A1, E],
        arg2: ResultMaybe[A2, E],
        arg3: ResultMaybe[A3, E],
        arg4: ResultMaybe[A4, E],
) -> ResultMaybe[R, E]:
    if isinstance(arg1, Fail):
        return arg1
    arg1_inner = arg1.value
    if isinstance(arg1_inner, Nothing):
        return cast(ResultMaybe[R, E], arg1)
    
    if isinstance(arg2, Fail):
        return arg2
    arg2_inner = arg2.value
    if isinstance(arg2_inner, Nothing):
        return cast(ResultMaybe[R, E], arg2)
    
    if isinstance(arg3, Fail):
        return arg3
    arg3_inner = arg3.value
    if isinstance(arg3_inner, Nothing):
        return cast(ResultMaybe[R, E], arg3)

    if isinstance(arg4, Fail):
        return arg4
    arg4_inner = arg4.value
    if isinstance(arg4_inner, Nothing):
        return cast(ResultMaybe[R, E], arg4)
    
    return Success(Just(fn(arg1_inner.value, arg2_inner.value, arg3_inner.value, arg4_inner.value)))


def lift(fn: Callable[..., R], *args: ResultMaybe[Any, Any]) -> ResultMaybe[R, Any]:
    unwrapped: list[Any] = list()
    for arg in args:
        if isinstance(arg, Fail):
            return arg
        arg_inner = arg.value
        if isinstance(arg_inner, Nothing):
            return arg
        unwrapped.append(arg_inner.value)
    return Success(Just(fn(*unwrapped)))
