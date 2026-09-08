from collections.abc import Callable
from typing import TypeVar

from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync  # type: ignore # noqa
from mafunca.aff.direct import ap
from mafunca._lazy_support import panic_on_coroutine
from mafunca.curry import curry2, curry3, curry4


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")
B = TypeVar("B")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: Aff[A1],
        arg2: Aff[A2]
) -> Aff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Aff.__name__, 'lift2')
    return ap(arg2, ap(arg1, _PureAsync(curry2(fn))))


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: Aff[A1],
        arg2: Aff[A2],
        arg3: Aff[A3]
) -> Aff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Aff.__name__, 'lift3')
    return ap(arg3, ap(arg2, ap(arg1, _PureAsync(curry3(fn)))))


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: Aff[A1],
        arg2: Aff[A2],
        arg3: Aff[A3],
        arg4: Aff[A4],
) -> Aff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Aff.__name__, 'lift4')
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, _PureAsync(curry4(fn))))))
