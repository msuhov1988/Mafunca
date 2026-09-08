from collections.abc import Callable
from typing import TypeVar

from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _BindAsync, _CatchAsync, _EnsureAsync  # type: ignore # noqa
import mafunca.aff.direct as ad
from mafunca._lazy_support import panic_on_coroutine


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")


def fmap(fn: Callable[[A], B]) -> Callable[[Aff[A]], Aff[B]]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Aff.__name__, 'fmap')

    def fmap_inner(effect: Aff[A]) -> Aff[B]:
        return _BindAsync(effect, lambda a: _PureAsync(fn(a)))
    
    return fmap_inner


def bind(fn: Callable[[A], Aff[B]]) -> Callable[[Aff[A]], Aff[B]]:
    """
        The function that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Aff.__name__, 'bind')

    def bind_inner(effect: Aff[A])  -> Aff[B]:
        return _BindAsync(effect, fn)

    return bind_inner


def catch_fmap(exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Callable[[Aff[A]], Aff[A]]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, Aff.__name__, 'catch_fmap')

    def catch_fmap_inner(effect: Aff[A]) -> Aff[A]:
        return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(catcher(exc)))

    return catch_fmap_inner


def catch_bind(exc_type: type[Exc], catcher: Callable[[Exc], Aff[A]]) -> Callable[[Aff[A]], Aff[A]]:
    """
        The catcher that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, Aff.__name__, 'catch_bind')

    def cathc_bind_inner(effect: Aff[A]) -> Aff[A]:
        return _CatchAsync(effect, exc_type, catcher)

    return cathc_bind_inner


def ensure(finalizer: Aff[None]) -> Callable[[Aff[A]], Aff[A]]:

    def ensure_inner(effect: Aff[A])  -> Aff[A]:
        return _EnsureAsync(effect, finalizer)

    return ensure_inner


def ap(effect: Aff[A]) -> Callable[[Aff[Callable[[A], B]]], Aff[B]]:

    def ap_inner(fn: Aff[Callable[[A], B]]) -> Aff[B]:
        return ad.bind(fn, lambda fn_inner: ad.fmap(effect, lambda val: fn_inner(val)))

    return ap_inner
