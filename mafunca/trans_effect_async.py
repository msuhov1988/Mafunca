from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import TypeVar, Generic, Never


from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Success, Fail
import mafunca.result_direct as rd
from mafunca.effect_async import Aff
from mafunca.effect_async import _PureAsync, _DelayAsync, _DelayThreadAsync, _RetryAsync  # type: ignore # noqa
from mafunca.effect_async import _BindAsync, _CatchAsync, _EnsureAsync  # type: ignore # noqa
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "AffResult",
    "pure_success",
    "pure_fail",
    "pure_result",
    "lift_effect",
    "delay",
    "delay_to_thread",
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
class AffResult(Generic[A, E]):
    """
        A transformer for ASYNCHRONOUS effects.

        Container for a composite value of the form 'EffectAsync[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: Aff[Result[A, E]]

    def fmap(self, fn: Callable[[A], B]) -> AffResult[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap')
        return AffResult(_BindAsync(self.inner, lambda res: _PureAsync(rd.fmap(res, fn))))

    def fmap_result(self, fn: Callable[[A], Result[B, E]]) -> AffResult[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap_result')
        return AffResult(_BindAsync(self.inner, lambda res: _PureAsync(rd.bind(res, fn))))

    def fmap_error(self, fn: Callable[[E], Enew]) -> AffResult[A, Enew]:
        """
            Only for SYNCHRONOUS functions - pure calculation

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap_error')
        return AffResult(_BindAsync(self.inner, lambda res: _PureAsync(rd.fmap_error(res, fn))))

    def bind(self, fn: Callable[[A], AffResult[B, E]]) -> AffResult[B, E]:
        """
            The function that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> Aff[Result[B, E]]:
            if isinstance(arg, Fail):
                return _PureAsync(arg)
            return fn(arg.value).inner

        return AffResult(_BindAsync(self.inner, continuation))

    def catch_fmap(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> AffResult[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_fmap')
        return AffResult(_CatchAsync(self.inner, exc_type, lambda exc: _PureAsync(Success(catcher(exc)))))

    def catch_fmap_result(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], Result[A, E]]
    ) -> AffResult[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_fmap_result')
        return AffResult(_CatchAsync(self.inner, exc_type, lambda exc: _PureAsync(catcher(exc))))

    def catch_bind(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], AffResult[A, E]]
    ) -> AffResult[A, E]:
        """
            The catcher that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect

            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return AffResult(_CatchAsync(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: Aff[None]) -> AffResult[A, E]:
        return AffResult(_EnsureAsync(self.inner, finalizer))


S = TypeVar("S")
F = TypeVar("F")
R = TypeVar("R")


def pure_success(value: S) -> AffResult[S, Never]:
    """Wraps a ready-made value"""
    return AffResult(_PureAsync(Success(value)))


def pure_fail(error: F) -> AffResult[Never, F]:
    """Wraps a ready-made error"""
    return AffResult(_PureAsync(Fail(error)))


def pure_result(result: Result[S, F]) -> AffResult[S, F]:
    """Wraps a ready-made Result value"""
    return AffResult(_PureAsync(result))


def lift_effect(effect: Aff[S]) -> AffResult[S, Never]:
    """Lift the effect to a transformer"""
    return AffResult(_BindAsync(effect, lambda a: _PureAsync(Success(a))))


def delay(
        fn: Callable[[], Awaitable[Result[S, F]]],
        wait_seconds: int | float | None = None
) -> AffResult[S, F]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution

        :raises ValidationError: incorrect wait_seconds parameter
    """
    return AffResult(_DelayAsync(fn, wait_seconds))


def delay_to_thread(fn: Callable[[], Result[S, F]]) -> AffResult[S, F]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, AffResult.__name__, 'delay_to_thread')
    return AffResult(_DelayThreadAsync(fn))


def retry(
        fn: Callable[[], Awaitable[Result[S, F]]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[S, F]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> AffResult[S, F]:
    """
    Attempting to repeat the effect under user-defined conditions.

    :param fn: ASYNCHRONOUS effect
    :param total_attempts: total number of attempts including the first one
    :param wait_seconds_on_attempt: a waiting timer for each attempt
    :param pause_seconds_between: function that takes the attempt number(from 1) and returns a pause in seconds
    :param retry_on_result: predicate on the result, if it returns True, the effect is repeated
    :param retry_on_exceptions: a tuple of exceptions under which the effect should be repeated
    :param step_name: step name for identification purposes

    :raises ValidationError: errors in basic validation of passed arguments
    """
    return AffResult(
        _RetryAsync(
            thunk=fn,
            total_attempts=total_attempts,
            wait_seconds_on_attempt=wait_seconds_on_attempt,
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


def ap(effect: AffResult[S, F], fn: AffResult[Callable[[S], R], F]) -> AffResult[R, F]:
    return fn.bind(lambda fn_inner: effect.fmap(lambda val: fn_inner(val)))


def lift2(
        fn: Callable[[S1, S2], R],
        arg1: AffResult[S1, F],
        arg2: AffResult[S2, F]
) -> AffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, AffResult.__name__, 'lift2')
    return ap(arg2, ap(arg1, pure_success(curry2(fn))))


def lift3(
        fn: Callable[[S1, S2, S3], R],
        arg1: AffResult[S1, F],
        arg2: AffResult[S2, F],
        arg3: AffResult[S3, F]
) -> AffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, AffResult.__name__, 'lift3')
    return ap(arg3, ap(arg2, ap(arg1, pure_success(curry3(fn)))))


def lift4(
        fn: Callable[[S1, S2, S3, S4], R],
        arg1: AffResult[S1, F],
        arg2: AffResult[S2, F],
        arg3: AffResult[S3, F],
        arg4: AffResult[S4, F],
) -> AffResult[R, F]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, AffResult.__name__, 'lift4')
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, pure_success(curry4(fn))))))
