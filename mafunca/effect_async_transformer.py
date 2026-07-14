from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import TypeVar, Generic, Never


from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err
from mafunca.effect_async import EffectAsync
from mafunca.effect_async import PureAsync, DelayAsync, DelayThreadAsync, RetryAsync  # noqa
from mafunca.effect_async import BindAsync, CatchAsync, EnsureAsync  # noqa


__all__ = [
    "EffectAsyncT",
    "pure",
    "lift_error",
    "lift_result",
    "lift_effect",
    "delay",
    "delay_to_thread",
    "retry"
]

A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")
NewE = TypeVar('NewE')


@dataclass(frozen=True, slots=True, repr=True)
class EffectAsyncT(Generic[A, E]):
    """
        A transformer for ASYNCHRONOUS effects.

        Container for a composite value of the form 'EffectAsync[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: EffectAsync[Result[A, E]]

    def map(self, fn: Callable[[A], B]) -> EffectAsyncT[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return EffectAsyncT(BindAsync(self.inner, lambda res: PureAsync(res.map(fn))))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> EffectAsyncT[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return EffectAsyncT(BindAsync(self.inner, lambda res: PureAsync(res.bind(fn))))

    def map_error(self, fn: Callable[[E], NewE]) -> EffectAsyncT[A, NewE]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map_error')
        return EffectAsyncT(BindAsync(self.inner, lambda res: PureAsync(res.map_error(fn))))

    def bind(self, fn: Callable[[A], EffectAsyncT[B, E]]) -> EffectAsyncT[B, E]:
        """
            The function that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> EffectAsync[Result[B, E]]:
            if isinstance(arg, Err):
                return PureAsync(arg)
            return fn(arg.value).inner

        return EffectAsyncT(BindAsync(self.inner, continuation))

    def catch_map(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], A]
    ) -> EffectAsyncT[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return EffectAsyncT(CatchAsync(self.inner, exc_type, lambda exc: PureAsync(Ok(catcher(exc)))))

    def catch_map_result(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], Result[A, E]]
    ) -> EffectAsyncT[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map_result')
        return EffectAsyncT(CatchAsync(self.inner, exc_type, lambda exc: PureAsync(catcher(exc))))

    def catch_bind(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], EffectAsyncT[A, E]]
    ) -> EffectAsyncT[A, E]:
        """
            The catcher that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return EffectAsyncT(CatchAsync(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: EffectAsync[None]) -> EffectAsyncT[A, E]:
        return EffectAsyncT(EnsureAsync(self.inner, finalizer))


def pure(value: A) -> EffectAsyncT[A, Never]:
    """Wraps a ready-made value"""
    return EffectAsyncT(PureAsync(Ok(value)))


def lift_error(error: E) -> EffectAsyncT[Never, E]:
    """Wraps a ready-made error"""
    return EffectAsyncT(PureAsync(Err(error)))


def lift_result(result: Result[A, E]) -> EffectAsyncT[A, E]:
    """Wraps a ready-made Result value"""
    return EffectAsyncT(PureAsync(result))


def lift_effect(effect: EffectAsync[A]) -> EffectAsyncT[A, Never]:
    """Lift the effect to a transformer"""
    return EffectAsyncT(BindAsync(effect, lambda a: PureAsync(Ok(a))))


def delay(
        fn: Callable[[], Awaitable[Result[A, E]]],
        wait_seconds: int | float | None = None
) -> EffectAsyncT[A, E]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution
        :raises ValidationError: incorrect wait_seconds parameter
    """
    return EffectAsyncT(DelayAsync(fn, wait_seconds))


def delay_to_thread(fn: Callable[[], Result[A, E]]) -> EffectAsyncT[A, E]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffectAsyncT.__name__, 'delay_to_thread')
    return EffectAsyncT(DelayThreadAsync(fn))


def retry(
        fn: Callable[[], Awaitable[Result[A, E]]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[A, E]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffectAsyncT[A, E]:
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
    return EffectAsyncT(
        RetryAsync(
            thunk=fn,
            total_attempts=total_attempts,
            wait_seconds_on_attempt=wait_seconds_on_attempt,
            pause_seconds_between=pause_seconds_between,
            retry_on_result=retry_on_result,
            retry_on_exceptions=retry_on_exceptions,
            step_name=step_name
        )
    )
