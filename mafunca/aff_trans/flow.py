from collections.abc import Callable
from typing import TypeVar

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result.build import Result, Success, Fail
import mafunca.result.direct as rd
from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _BindAsync, _CatchAsync, _EnsureAsync  # type: ignore # noqa
from mafunca.aff_trans.build import AffResult
import mafunca.aff_trans.direct as tad


A = TypeVar("A", covariant=True)
E = TypeVar("E", covariant=True)
B = TypeVar("B")
Enew = TypeVar('Enew')
Exc = TypeVar("Exc", bound=Exception)


def fmap(fn: Callable[[A], B]) -> Callable[[AffResult[A, E]], AffResult[B, E]]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap')

    def fmap_inner(effect: AffResult[A, E]) -> AffResult[B, E]:
        return _BindAsync(effect, lambda res: _PureAsync(rd.fmap(res, fn)))

    return fmap_inner


def fmap_error(fn: Callable[[E], Enew]) -> Callable[[AffResult[A, E]], AffResult[A, Enew]]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap_error')

    def fmap_error_inner(effect: AffResult[A, E]) -> AffResult[A, Enew]: 
        return _BindAsync(effect, lambda res: _PureAsync(rd.fmap_error(res, fn)))

    return fmap_error_inner


def fmap_result(fn: Callable[[A], Result[B, E]]) -> Callable[[AffResult[A, E]], AffResult[B, E]]:
    """
        Only for SYNCHRONOUS functions - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'fmap_result')

    def fmap_result_inner(effect: AffResult[A, E]) -> AffResult[B, E]:
        return _BindAsync(effect, lambda res: _PureAsync(rd.bind(res, fn)))

    return fmap_result_inner


def bind(fn: Callable[[A], AffResult[B, E]]) -> Callable[[AffResult[A, E]], AffResult[B, E]]:
    """
        The function that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, 'AffResult', 'bind')

    def bind_inner(effect: AffResult[A, E]) -> AffResult[B, E]:
        def continuation(arg: Result[A, E]) -> Aff[Result[B, E]]:
            if isinstance(arg, Fail):
                return _PureAsync(arg)
            return fn(arg.value)

        return _BindAsync(effect, continuation)

    return bind_inner


def catch_fmap(exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Callable[[AffResult[A, E]], AffResult[A, E]]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_fmap')

    def catch_map_inner(effect: AffResult[A, E]) -> AffResult[A, E]:
        return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(Success(catcher(exc))))

    return catch_map_inner


def catch_fmap_result(        
        exc_type: type[Exc],
        catcher: Callable[[Exc], Result[A, E]]
    ) -> Callable[[AffResult[A, E]], AffResult[A, E]]:
    """
        Only for SYNCHRONOUS catchers - pure calculation

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_fmap_result')

    def catch_fmap_result_inner(effect: AffResult[A, E]) -> AffResult[A, E]:
        return _CatchAsync(effect, exc_type, lambda exc: _PureAsync(catcher(exc)))

    return catch_fmap_result_inner


def catch_bind(        
        exc_type: type[Exc],
        catcher: Callable[[Exc], AffResult[A, E]]
    ) -> Callable[[AffResult[A, E]], AffResult[A, E]]:
    """
        The catcher that returns the effect must be SYNCHRONOUS.
        Asynchrony is assumed inside the effect

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(catcher, 'AffResult', 'catch_bind')

    def catch_bind_inner(effect: AffResult[A, E]) -> AffResult[A, E]:
        return _CatchAsync(effect, exc_type, lambda exc: catcher(exc))

    return catch_bind_inner


def ensure_soft(finalizer: Aff[None]) -> Callable[[AffResult[A, E]], AffResult[A, E]]:
    """
        'Soft' finalizer.

        It behaves like `finally` in all normal execution scenarios:

        - successful completion
        - exceptions that are subclasses of `Exception`
        - standard asynchronous cancellation via `asyncio.CancelledError`
    """
    def ensure_inner(effect: AffResult[A, E]) -> AffResult[A, E]:
        return _EnsureAsync(effect, finalizer)

    return ensure_inner


def ap(effect: AffResult[A, E]) -> Callable[[AffResult[Callable[[A], B], E]], AffResult[B, E]]:

    def ap_inner(fn: AffResult[Callable[[A], B], E]) -> AffResult[B, E]:
        return tad.bind(fn, lambda fn_inner: tad.fmap(effect, lambda val: fn_inner(val)))

    return ap_inner
