from collections.abc import Callable
from typing import TypeVar, Never


from mafunca._lazy_support import panic_on_coroutine
from mafunca.result.build import Result, Success, Fail
import mafunca.result.direct as rd
from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _BindAsync, _CatchAsync, _EnsureAsync  # type: ignore # noqa
from mafunca.aff_trans.build import AffResult


A = TypeVar("A", covariant=True)
E = TypeVar("E", covariant=True)
B = TypeVar("B")
Enew = TypeVar('Enew')
Exc = TypeVar("Exc", bound=Exception)


def fmap(effect: AffResult[A, E], fn: Callable[[A], B]) -> AffResult[B, E]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap')
    return _BindAsync(effect, lambda res: _PureAsync(rd.fmap(res, fn)))


def fmap_error(effect: AffResult[A, E], fn: Callable[[E], Enew]) -> AffResult[A, Enew]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap_error')
    return _BindAsync(effect, lambda res: _PureAsync(rd.fmap_error(res, fn)))


def fmap_result(effect: AffResult[A, E], fn: Callable[[A], Result[B, E]]) -> AffResult[B, E]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap_result')
    return _BindAsync(effect, lambda res: _PureAsync(rd.bind(res, fn)))


def bind(effect: AffResult[A, E], fn: Callable[[A], AffResult[B, E]]) -> AffResult[B, E]:
    """
        The function that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'bind')

    def continuation(arg: Result[A, E]) -> Aff[Result[B, E]]:
        if isinstance(arg, Fail):
            return _PureAsync(arg)
        return fn(arg.value)

    return _BindAsync(effect, continuation)


def catch_fmap(effect: AffResult[A, E], exc_type: type[Exc], catcher: Callable[[Exc], A]) -> AffResult[A, E]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_fmap')
    return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(Success(catcher(exc))))


def catch_fmap_result(
        effect: AffResult[A, E],
        exc_type: type[Exc],
        catcher: Callable[[Exc], Result[A, E]]
    ) -> AffResult[A, E]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_fmap_result')
    return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(catcher(exc)))


def catch_bind(
        effect: AffResult[A, E],
        exc_type: type[Exc],
        catcher: Callable[[Exc], AffResult[A, E]]
    ) -> AffResult[A, E]:
    """
        The catcher that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_bind')
    return _CatchAsync(effect, exc_type, lambda exc: catcher(exc))


def ensure_soft(effect: AffResult[A, E], finalizer: Aff[None] | AffResult[None, Never]) -> AffResult[A, E]:    
    return _EnsureAsync(effect, finalizer)


def ap(effect: AffResult[A, E], fn: AffResult[Callable[[A], B], E]) -> AffResult[B, E]:
    return bind(fn, lambda fn_inner: fmap(effect, lambda val: fn_inner(val)))
