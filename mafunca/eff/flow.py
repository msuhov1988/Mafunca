from collections.abc import Callable
from typing import TypeVar

from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Bind, _Catch, _Ensure  # type: ignore # noqa
import mafunca.eff.direct as ed
from mafunca._lazy_support import panic_on_coroutine


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)


def fmap(fn: Callable[[A], B]) -> Callable[[Eff[A]], Eff[B]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'fmap')

    def fmap_inner(effect: Eff[A]) -> Eff[B]:
        return _Bind(effect, lambda a: _Pure(fn(a)))

    return fmap_inner


def bind(fn: Callable[[A], Eff[B]]) -> Callable[[Eff[A]], Eff[B]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'bind')

    def bind_inner(effect: Eff[A]) -> Eff[B]:
        return _Bind(effect, fn)

    return bind_inner


def catch_fmap(exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Callable[[Eff[A]], Eff[A]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, Eff.__name__, 'catch_fmap')

    def catch_fmap_inner(effect: Eff[A]) -> Eff[A]:
        return _Catch(effect, exc_type, lambda exc: _Pure(catcher(exc)))

    return catch_fmap_inner


def catch_bind(exc_type: type[Exc], catcher: Callable[[Exc], Eff[A]]) -> Callable[[Eff[A]], Eff[A]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, Eff.__name__, 'catch_bind')

    def catch_bind_inner(effect: Eff[A])  -> Eff[A]:
        return _Catch(effect, exc_type, catcher)

    return catch_bind_inner


def ensure_soft(finalizer: Eff[None]) -> Callable[[Eff[A]], Eff[A]]:
    """
        'Soft' finalizer.

        It behaves like `finally` in all normal execution scenarios:

        - successful completion
        - exceptions that are subclasses of `Exception`
    """
    def ensure_inner(effect: Eff[A]) -> Eff[A]:
        return _Ensure(effect, finalizer)

    return ensure_inner


def ap(effect: Eff[A]) -> Callable[[Eff[Callable[[A], B]]], Eff[B]]:

    def ap_inner(fn: Eff[Callable[[A], B]]) -> Eff[B]: 
        return ed.bind(fn, lambda fn_inner: ed.fmap(effect, lambda val: fn_inner(val)))

    return ap_inner
