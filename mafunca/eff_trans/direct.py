from collections.abc import Callable
from typing import TypeVar, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result.build import Result, Success, Fail
import mafunca.result.direct as rd
from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Bind, _Catch, _Ensure  # type: ignore # noqa
from mafunca.eff_trans.build import EffResult


A = TypeVar("A")
E = TypeVar("E")
B = TypeVar("B")
Enew = TypeVar('Enew')
Exc = TypeVar("Exc", bound=Exception)


def fmap(effect: EffResult[A, E], fn: Callable[[A], B]) -> EffResult[B, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'fmap')
    return _Bind(effect, lambda res: _Pure(rd.fmap(res, fn)))


def fmap_error(effect: EffResult[A, E], fn: Callable[[E], Enew]) -> EffResult[A, Enew]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'fmap_error')
    return _Bind(effect, lambda res: _Pure(rd.fmap_error(res, fn)))


def fmap_result(effect: EffResult[A, E], fn: Callable[[A], Result[B, E]]) -> EffResult[B, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'fmap_result')
    return _Bind(effect, lambda res: _Pure(rd.bind(res, fn)))


def bind(effect: EffResult[A, E], fn: Callable[[A], EffResult[B, E]]) -> EffResult[B, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'bind')

    def continuation(arg: Result[A, E]) -> EffResult[B, E]:
        if isinstance(arg, Fail):
            return _Pure(arg)
        return fn(arg.value)

    return _Bind(effect, continuation)


def catch_fmap(effect: EffResult[A, E], exc_type: type[Exc], catcher: Callable[[Exc], A]) -> EffResult[A, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, 'EffResult', 'catch_fmap')
    return _Catch(effect, exc_type, lambda exc: _Pure(Success(catcher(exc))))


def catch_fmap_result(
        effect: EffResult[A, E],
        exc_type: type[Exc],
        catcher: Callable[[Exc], Result[A, E]]
) -> EffResult[A, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, 'EffResult', 'catch_fmap_result')
    return _Catch(effect, exc_type, lambda exc: _Pure(catcher(exc)))


def catch_bind(
        effect: EffResult[A, E],
        exc_type: type[Exc],
        catcher: Callable[[Exc], EffResult[A, E]]
) -> EffResult[A, E]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, 'EffResult', 'catch_bind')
    return _Catch(effect, exc_type, lambda exc: catcher(exc))


def ensure_soft(effect: EffResult[A, E], finalizer: Eff[None] | EffResult[None, Never]) -> EffResult[A, E]:    
    return _Ensure(effect, finalizer)


def ap(effect: EffResult[A, E], fn: EffResult[Callable[[A], B], E]) -> EffResult[B, E]:
    return bind(fn, lambda fn_inner: fmap(effect, lambda val: fn_inner(val)))
