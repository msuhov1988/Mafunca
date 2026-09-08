from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, Generic, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Success, Fail
import mafunca.result_direct as rd
from mafunca.effect_sync import Eff
from mafunca.effect_sync import _Pure, _Delay, _Retry  # type: ignore # noqa
from mafunca.effect_sync import _Bind, _Catch, _Ensure  # type: ignore # noqa
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "EffResult",
    "pure_success",
    "pure_fail",
    "pure_result",
    "lift_effect",    
    "delay",
    "retry",
    "ap",
    "lift2",
    "lift3",
    "lift4",
]


A = TypeVar("A", covariant=True)
E = TypeVar("E", covariant=True)
B = TypeVar("B")
Enew = TypeVar('Enew')
Exc = TypeVar("Exc", bound=Exception)


@dataclass(frozen=True, slots=True, repr=True)
class EffResult(Generic[A, E]):
    """
        A transformer for SYNCHRONOUS ONLY effects.

        Container for a composite value of the form 'Eff[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: Eff[Result[A, E]]

    def fmap(self, fn: Callable[[A], B]) -> EffResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap')
        return EffResult(_Bind(self.inner, lambda res: _Pure(rd.fmap(res, fn))))

    def fmap_result(self, fn: Callable[[A], Result[B, E]]) -> EffResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap_result')
        return EffResult(_Bind(self.inner, lambda res: _Pure(rd.bind(res, fn))))

    def fmap_error(self, fn: Callable[[E], Enew]) -> EffResult[A, Enew]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap_error')
        return EffResult(_Bind(self.inner, lambda res: _Pure(rd.fmap_error(res, fn))))

    def bind(self, fn: Callable[[A], EffResult[B, E]]) -> EffResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> Eff[Result[B, E]]:
            if isinstance(arg, Fail):
                return _Pure(arg)
            return fn(arg.value).inner

        return EffResult(_Bind(self.inner, continuation))

    def catch_fmap(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> EffResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_fmap')
        return EffResult(_Catch(self.inner, exc_type, lambda exc: _Pure(Success(catcher(exc)))))

    def catch_fmap_result(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], Result[A, E]]
    ) -> EffResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_fmap_result')
        return EffResult(_Catch(self.inner, exc_type, lambda exc: _Pure(catcher(exc))))

    def catch_bind(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], EffResult[A, E]]
    ) -> EffResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return EffResult(_Catch(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: Eff[None]) -> EffResult[A, E]:
        return EffResult(_Ensure(self.inner, finalizer))


S = TypeVar("S")
F = TypeVar("F")
R = TypeVar("R")


def pure_success(value: S) -> EffResult[S, Never]:
    """Wraps a ready-made value"""
    return EffResult(_Pure(Success(value)))


def pure_fail(err: F) -> EffResult[Never, F]:
    """Wraps a ready-made error"""
    return EffResult(_Pure(Fail(err)))


def pure_result(result: Result[S, F]) -> EffResult[S, F]:
    """Wraps a ready-made Result value"""
    return EffResult(_Pure(result))


def lift_effect(effect: Eff[S]) -> EffResult[S, Never]:
    """Lift the effect to a transformer"""
    return EffResult(_Bind(effect, lambda a: _Pure(Success(a))))


def delay(fn: Callable[[], Result[S, F]]) -> EffResult[S, F]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffResult.__name__, 'delay')
    return EffResult(_Delay(fn))


def retry(
        fn: Callable[[], Result[S, F]],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[S, F]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffResult[S, F]:
    """
    Attempting to repeat the effect under user-defined conditions.

    :param fn: SYNCHRONOUS effect
    :param total_attempts: total number of attempts including the first one
    :param pause_seconds_between: function that takes the attempt number(from 1) and returns a pause in seconds
    :param retry_on_result: predicate on the result, if it returns True, the effect is repeated
    :param retry_on_exceptions: a tuple of exceptions under which the effect should be repeated
    :param step_name: step name for identification purposes

    :raises MonadError: coroutine functions are not allowed
    :raises ValidationError: errors in basic validation of passed arguments
    """
    panic_on_coroutine(fn, EffResult.__name__, 'retry')
    return EffResult(
        _Retry(
            thunk=fn,
            total_attempts=total_attempts,
            pause_seconds_between=pause_seconds_between,
            retry_on_result=retry_on_result,
            retry_on_exceptions=retry_on_exceptions,
            step_name=step_name
        )
    )


S1 = TypeVar("S1")
S2 = TypeVar("S2")
S3 = TypeVar("S3")
S4 = TypeVar("S4")


def ap(effect: EffResult[S, F], fn: EffResult[Callable[[S], R], F]) -> EffResult[R, F]:
    return fn.bind(lambda fn_inner: effect.fmap(lambda val: fn_inner(val)))


def lift2(
        fn: Callable[[S1, S2], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F]
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, EffResult.__name__, 'lift2')
    return ap(arg2, ap(arg1, pure_success(curry2(fn))))


def lift3(
        fn: Callable[[S1, S2, S3], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F],
        arg3: EffResult[S3, F]
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, EffResult.__name__, 'lift3')
    return ap(arg3, ap(arg2, ap(arg1, pure_success(curry3(fn)))))


def lift4(
        fn: Callable[[S1, S2, S3, S4], R],
        arg1: EffResult[S1, F],
        arg2: EffResult[S2, F],
        arg3: EffResult[S3, F],
        arg4: EffResult[S4, F],
) -> EffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, EffResult.__name__, 'lift4')
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, pure_success(curry4(fn))))))
