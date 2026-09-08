from collections.abc import Callable
from typing import TypeVar

from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure  # type: ignore # noqa
from mafunca.eff.direct import ap
from mafunca._lazy_support import panic_on_coroutine
from mafunca.curry import curry2, curry3, curry4


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")
B = TypeVar("B")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: Eff[A1],
        arg2: Eff[A2]
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift2')
    return ap(arg2, ap(arg1, _Pure(curry2(fn))))


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: Eff[A1],
        arg2: Eff[A2],
        arg3: Eff[A3]
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift3')
    return ap(arg3, ap(arg2, ap(arg1, _Pure(curry3(fn)))))


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: Eff[A1],
        arg2: Eff[A2],
        arg3: Eff[A3],
        arg4: Eff[A4],
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift4')
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, _Pure(curry4(fn))))))
