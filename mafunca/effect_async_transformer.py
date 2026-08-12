from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import TypeVar, Generic, Never


from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err
from mafunca.effect_async import Aff
from mafunca.effect_async import PureAsync, DelayAsync, DelayThreadAsync, RetryAsync  # noqa
from mafunca.effect_async import BindAsync, CatchAsync, EnsureAsync  # noqa
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "AffResult",
    "pure",
    "lift_error",
    "lift_result",
    "lift_effect",
    "delay",
    "delay_to_thread",
    "retry",
    "lift2",
    "lift3",
    "lift4",
]

A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")
NewE = TypeVar('NewE')


@dataclass(frozen=True, slots=True, repr=True)
class AffResult(Generic[A, E]):
    """
        A transformer for ASYNCHRONOUS effects.

        Container for a composite value of the form 'EffectAsync[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: Aff[Result[A, E]]

    def map(self, fn: Callable[[A], B]) -> AffResult[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return AffResult(BindAsync(self.inner, lambda res: PureAsync(res.map(fn))))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> AffResult[B, E]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return AffResult(BindAsync(self.inner, lambda res: PureAsync(res.bind(fn))))

    def map_error(self, fn: Callable[[E], NewE]) -> AffResult[A, NewE]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map_error')
        return AffResult(BindAsync(self.inner, lambda res: PureAsync(res.map_error(fn))))

    def bind(self, fn: Callable[[A], AffResult[B, E]]) -> AffResult[B, E]:
        """
            The function that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> Aff[Result[B, E]]:
            if isinstance(arg, Err):
                return PureAsync(arg)
            return fn(arg.value).inner

        return AffResult(BindAsync(self.inner, continuation))

    def catch_map(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], A]
    ) -> AffResult[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return AffResult(CatchAsync(self.inner, exc_type, lambda exc: PureAsync(Ok(catcher(exc)))))

    def catch_map_result(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], Result[A, E]]
    ) -> AffResult[A, E]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map_result')
        return AffResult(CatchAsync(self.inner, exc_type, lambda exc: PureAsync(catcher(exc))))

    def catch_bind(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], AffResult[A, E]]
    ) -> AffResult[A, E]:
        """
            The catcher that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return AffResult(CatchAsync(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: Aff[None]) -> AffResult[A, E]:
        return AffResult(EnsureAsync(self.inner, finalizer))


def pure(value: A) -> AffResult[A, Never]:
    """Wraps a ready-made value"""
    return AffResult(PureAsync(Ok(value)))


def lift_error(error: E) -> AffResult[Never, E]:
    """Wraps a ready-made error"""
    return AffResult(PureAsync(Err(error)))


def lift_result(result: Result[A, E]) -> AffResult[A, E]:
    """Wraps a ready-made Result value"""
    return AffResult(PureAsync(result))


def lift_effect(effect: Aff[A]) -> AffResult[A, Never]:
    """Lift the effect to a transformer"""
    return AffResult(BindAsync(effect, lambda a: PureAsync(Ok(a))))


def delay(
        fn: Callable[[], Awaitable[Result[A, E]]],
        wait_seconds: int | float | None = None
) -> AffResult[A, E]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution
        :raises ValidationError: incorrect wait_seconds parameter
    """
    return AffResult(DelayAsync(fn, wait_seconds))


def delay_to_thread(fn: Callable[[], Result[A, E]]) -> AffResult[A, E]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, AffResult.__name__, 'delay_to_thread')
    return AffResult(DelayThreadAsync(fn))


def retry(
        fn: Callable[[], Awaitable[Result[A, E]]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[A, E]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> AffResult[A, E]:
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


def _ap(wrapped_fn: AffResult[Callable[[A], B], E], wrapped_val: AffResult[A, E]) -> AffResult[B, E]:
    return wrapped_fn.bind(lambda fn: wrapped_val.map(lambda val: fn(val)))


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: AffResult[A1, E],
        arg2: AffResult[A2, E]
) -> AffResult[B, E]:
    return _ap(_ap(pure(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: AffResult[A1, E],
        arg2: AffResult[A2, E],
        arg3: AffResult[A3, E]
) -> AffResult[B, E]:
    return _ap(_ap(_ap(pure(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: AffResult[A1, E],
        arg2: AffResult[A2, E],
        arg3: AffResult[A3, E],
        arg4: AffResult[A4, E],
) -> AffResult[B, E]:
    return _ap(_ap(_ap(_ap(pure(curry4(fn)), arg1), arg2), arg3), arg4)
