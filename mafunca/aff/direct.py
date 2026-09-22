from collections.abc import Callable
from typing import TypeVar

from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _BindAsync, _CatchAsync, _EnsureAsync, _BracketAsync  # type: ignore # noqa
from mafunca._lazy_support import panic_on_coroutine


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=BaseException)
E = TypeVar("E")


def fmap(effect: Aff[A], fn: Callable[[A], B]) -> Aff[B]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Aff.__name__, 'fmap')
    return _BindAsync(effect, lambda a: _PureAsync(fn(a)))


def bind(effect: Aff[A], fn: Callable[[A], Aff[B]]) -> Aff[B]:
    """
        The function that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect
    """
    return _BindAsync(effect, fn)


def catch_fmap(effect: Aff[A], exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Aff[A]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, Aff.__name__, 'catch_fmap')
    return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(catcher(exc)))


def catch_bind(effect: Aff[A], exc_type: type[Exc], catcher: Callable[[Exc], Aff[A]]) -> Aff[A]:
    """
        The catcher that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect
    """   
    return _CatchAsync(effect, exc_type, catcher)


def ensure_soft(effect: Aff[A], finalizer: Aff[None]) -> Aff[A]:    
    return _EnsureAsync(effect, finalizer)


def bracket(
        acquire: Aff[A], 
        use: Callable[[A], Aff[B]], 
        release: Callable[[A], Aff[None]]
) -> Aff[B]:
    return _BracketAsync(acquire, use, release)


def ap(effect: Aff[A], fn: Aff[Callable[[A], B]]) -> Aff[B]:
    return bind(fn, lambda fn_inner: fmap(effect, lambda val: fn_inner(val)))
