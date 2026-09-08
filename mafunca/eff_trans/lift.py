from collections.abc import Callable
from typing import TypeVar

from mafunca._lazy_support import panic_on_coroutine
from mafunca.eff_trans.build import EffResult, pure_success
from mafunca.eff_trans.direct import ap
from mafunca.curry import curry2, curry3, curry4


S1 = TypeVar("S1")
S2 = TypeVar("S2")
S3 = TypeVar("S3")
S4 = TypeVar("S4")
F = TypeVar("F")
R = TypeVar("R")


def lift2(
        fn: Callable[[S1, S2], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F]
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'lift2')     
    return ap(arg2, ap(arg1, pure_success(curry2(fn))))


def lift3(
        fn: Callable[[S1, S2, S3], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F],
        arg3: EffResult[S3, F]
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'lift3')    
    return ap(arg3, ap(arg2, ap(arg1, pure_success(curry3(fn)))))


def lift4(
        fn: Callable[[S1, S2, S3, S4], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F],
        arg3: EffResult[S3, F],
        arg4: EffResult[S4, F],
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'lift4')    
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, pure_success(curry4(fn))))))
