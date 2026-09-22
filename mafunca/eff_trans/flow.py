from collections.abc import Callable
from typing import TypeVar, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result.build import Result, Success, Fail
import mafunca.result.direct as rd
from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Bind, _Catch, _Ensure, _Bracket  # type: ignore # noqa
from mafunca.eff_trans.build import EffResult
import mafunca.eff_trans.direct as ted


A = TypeVar("A")
E = TypeVar("E")
B = TypeVar("B")
Enew = TypeVar('Enew')
Exc = TypeVar("Exc", bound=BaseException)


def fmap(fn: Callable[[A], B]) -> Callable[[EffResult[A, E]], EffResult[B, E]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'fmap')

    def fmap_inner(effect: EffResult[A, E]) -> EffResult[B, E]:
        return _Bind(effect, lambda res: _Pure(rd.fmap(res, fn)))

    return fmap_inner


def fmap_error(fn: Callable[[E], Enew]) -> Callable[[EffResult[A, E]], EffResult[A, Enew]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(fn, 'EffResult', 'fmap_error')

    def fmap_error_inner(effect: EffResult[A, E]) -> EffResult[A, Enew]:
        return _Bind(effect, lambda res: _Pure(rd.fmap_error(res, fn)))
    
    return fmap_error_inner


def fmap_result(fn: Callable[[A], Result[B, E]]) -> Callable[[EffResult[A, E]], EffResult[B, E]]:    

    def fmap_result_inner(effect: EffResult[A, E])  -> EffResult[B, E]:
        return _Bind(effect, lambda res: _Pure(rd.bind(res, fn)))

    return fmap_result_inner


def bind(fn: Callable[[A], EffResult[B, E]]) -> Callable[[EffResult[A, E]], EffResult[B, E]]:    

    def bind_inner(effect: EffResult[A, E]) -> EffResult[B, E]:
        def continuation(arg: Result[A, E]) -> EffResult[B, E]:
            if isinstance(arg, Fail):
                return _Pure(arg)
            return fn(arg.value)

        return _Bind(effect, continuation)

    return bind_inner


def catch_fmap(
        exc_type: type[Exc], 
        catcher: Callable[[Exc], A]
    ) -> Callable[[EffResult[A, E]], EffResult[A, E]]:
    """:raises MonadError: coroutine functions are not allowed"""
    panic_on_coroutine(catcher, 'EffResult', 'catch_fmap')

    def catch_fmap_inner(effect: EffResult[A, E]) -> EffResult[A, E]:
        return _Catch(effect, exc_type, lambda exc: _Pure(Success(catcher(exc))))

    return catch_fmap_inner


def catch_fmap_result(
        exc_type: type[Exc], 
        catcher: Callable[[Exc], Result[A, E]]
    ) -> Callable[[EffResult[A, E]], EffResult[A, E]]:    

    def catch_fmap_result_inner(effect: EffResult[A, E]) -> EffResult[A, E]:
        return _Catch(effect, exc_type, lambda exc: _Pure(catcher(exc)))

    return catch_fmap_result_inner


def catch_bind(        
        exc_type: type[Exc],
        catcher: Callable[[Exc], EffResult[A, E]]
    ) -> Callable[[EffResult[A, E]], EffResult[A, E]]:    

    def catch_bind_inner(effect: EffResult[A, E]) -> EffResult[A, E]:
        return _Catch(effect, exc_type, lambda exc: catcher(exc))

    return catch_bind_inner


def ensure_soft(finalizer: Eff[None] | EffResult[None, Never]) -> Callable[[EffResult[A, E]], EffResult[A, E]]:
    
    def ensure_soft_inner(effect: EffResult[A, E]) -> EffResult[A, E]:
        return _Ensure(effect, finalizer)

    return ensure_soft_inner


def bracket(        
        use: Callable[[A], EffResult[B, E]], 
        release: Callable[[A], Eff[None] | EffResult[None, Never]]
) -> Callable[[EffResult[A, E]], EffResult[B, E]]:

    def bracket_inner(acquire: EffResult[A, E]) -> EffResult[B, E]:

        def use_continuation(arg: Result[A, E]) -> EffResult[B, E]:
            res = rd.fmap(arg, use)
            return rd.fold(res, on_success=lambda s: s, on_fail=lambda e: _Pure(Fail(e)))

        def release_continuation(arg: Result[A, E]) -> Eff[None] | EffResult[None, E]:
            res = rd.fmap(arg, release)
            return rd.fold(res, on_success=lambda s: s, on_fail=lambda e: _Pure(Fail(e)))
        
        return _Bracket(acquire, use_continuation, release_continuation,)

    return bracket_inner


def ap(effect: EffResult[A, E]) -> Callable[[EffResult[Callable[[A], B], E]], EffResult[B, E]]:

    def ap_inner(fn: EffResult[Callable[[A], B], E]) -> EffResult[B, E]:
        return ted.bind(fn, lambda fn_inner: ted.fmap(effect, lambda val: fn_inner(val)))

    return ap_inner
