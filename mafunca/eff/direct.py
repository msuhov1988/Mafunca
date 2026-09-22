from collections.abc import Callable
from typing import TypeVar

from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Bind, _Catch, _Ensure  # type: ignore # noqa
from mafunca._lazy_support import panic_on_coroutine


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)


def fmap(effect: Eff[A], fn: Callable[[A], B]) -> Eff[B]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'fmap')
    return _Bind(effect, lambda a: _Pure(fn(a)))


def bind(effect: Eff[A], fn: Callable[[A], Eff[B]]) -> Eff[B]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'bind')
    return _Bind(effect, fn)


def catch_fmap(effect: Eff[A], exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Eff[A]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, Eff.__name__, 'catch_fmap')
    return _Catch(effect, exc_type, lambda exc: _Pure(catcher(exc)))


def catch_bind(effect: Eff[A], exc_type: type[Exc], catcher: Callable[[Exc], Eff[A]]) -> Eff[A]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, Eff.__name__, 'catch_bind')
    return _Catch(effect, exc_type, catcher)


def ensure_soft(effect: Eff[A], finalizer: Eff[None]) -> Eff[A]:    
    return _Ensure(effect, finalizer)


def ap(effect: Eff[A], fn: Eff[Callable[[A], B]]) -> Eff[B]:
    return bind(fn, lambda fn_inner: fmap(effect, lambda val: fn_inner(val)))
