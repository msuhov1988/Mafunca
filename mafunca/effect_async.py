from __future__ import annotations
from dataclasses import dataclass
import inspect
from collections.abc import Callable, Awaitable
from typing import TypeVar, Generic, Never

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err

__all__ = [
    "EffectAsync",
    "pure",
    "delay",
    "delay_to_thread",
    "retry",
    "EffectAsyncT",
    "pure_t",
    "error_t",
    "lift_result_t",
    "lift_effect_t",
    "delay_t",
    "delay_to_thread_t",
    "retry_t"
]

A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")
NewE = TypeVar('NewE')


class EffectAsync(Generic[A]):
    """
        A monad for ASYNCHRONOUS effects.
        Lazy: not executed until the corresponding executor is called.
    """

    def map(self, fn: Callable[[A], B]) -> EffectAsync[B]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return BindAsync(self, lambda a: PureAsync(fn(a)))

    def bind(self, fn: Callable[[A], EffectAsync[B]]) -> EffectAsync[B]:
        """
            The function that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return BindAsync(self, fn)

    def catch_map(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], A]
    ) -> EffectAsync[A]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return CatchAsync(self, exc_type, lambda exc: PureAsync(catcher(exc)))

    def catch_bind(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], EffectAsync[A]]
    ) -> EffectAsync[A]:
        """
            The catcher that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return CatchAsync(self, exc_type, catcher)

    def ensure(self, finalizer: EffectAsync[None]) -> EffectAsync[A]:
        return EnsureAsync(self, finalizer)


@dataclass(frozen=True, slots=True, repr=True)
class PureAsync(Generic[A], EffectAsync[A]):
    value: A


class DelayAsync(Generic[A], EffectAsync[A]):
    __slots__ = ('thunk', 'wait_seconds')

    def __init__(
            self,
            thunk: Callable[[], Awaitable[A]],
            wait_seconds: int | float | None
    ):
        if wait_seconds is not None:
            if not isinstance(wait_seconds, (int, float)) or wait_seconds <= 0:
                raise ValidationError("wait_seconds must be a positive number")
        self.thunk = thunk
        self.wait_seconds = wait_seconds


@dataclass(frozen=True, slots=True, repr=True)
class DelayThreadAsync(Generic[A], EffectAsync[A]):
    thunk: Callable[[], A]


class RetryAsync(Generic[A], EffectAsync[A]):
    __slots__ = (
        "thunk",
        "total_attempts",
        "wait_seconds_on_attempt",
        "pause_seconds_between",
        "retry_on_result",
        "retry_on_exceptions",
        "step_name"
    )

    def __init__(
            self,
            thunk: Callable[[], Awaitable[A]],
            total_attempts: int,
            wait_seconds_on_attempt: int | float | None,
            pause_seconds_between: Callable[[int], int | float],
            retry_on_result: Callable[[A], bool],
            retry_on_exceptions: tuple[type[Exception], ...],
            step_name: str
    ):
        if not isinstance(total_attempts, int) or total_attempts < 1:
            raise ValidationError("total_attempts must be a positive integer")
        if wait_seconds_on_attempt is not None:
            if not isinstance(wait_seconds_on_attempt, (int, float)) or wait_seconds_on_attempt <= 0:
                raise ValidationError("wait_seconds_on_attempt must be a positive number")
        if not callable(pause_seconds_between) or inspect.iscoroutinefunction(pause_seconds_between):
            raise ValidationError("pause_seconds_between must be a SYNC callable object")
        if not callable(retry_on_result) or inspect.iscoroutinefunction(retry_on_result):
            raise ValidationError("retry_on_result must be a SYNC callable object")
        if not isinstance(retry_on_exceptions, tuple):
            raise ValidationError("retry_on_exceptions must be a tuple")
        if retry_on_exceptions and not all(issubclass(e, Exception) for e in retry_on_exceptions):
            raise ValidationError("all elements of retry_on_exceptions must be subclasses of Exception")
        self.thunk = thunk
        self.total_attempts = total_attempts
        self.wait_seconds_on_attempt = wait_seconds_on_attempt
        self.pause_seconds_between = pause_seconds_between
        self.retry_on_result = retry_on_result
        self.retry_on_exceptions = retry_on_exceptions
        self.step_name = step_name


@dataclass(frozen=True, slots=True, repr=True)
class BindAsync(Generic[A, B], EffectAsync[B]):
    current: EffectAsync[A]
    continuation: Callable[[A], EffectAsync[B]]


@dataclass(frozen=True, slots=True, repr=True)
class CatchAsync(Generic[A, E], EffectAsync[A]):
    current: EffectAsync[A]
    exc_type: type[E]
    catcher: Callable[[E], EffectAsync[A]]


@dataclass(frozen=True, slots=True, repr=True)
class EnsureAsync(Generic[A], EffectAsync[A]):
    current: EffectAsync[A]
    finalizer: EffectAsync[None]


def pure(value: A) -> EffectAsync[A]:
    """Wraps a ready-made value"""
    return PureAsync(value)


def delay(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None = None
) -> EffectAsync[A]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution
        :raises ValidationError: incorrect wait_seconds parameter
    """
    return DelayAsync(fn, wait_seconds)


def delay_to_thread(fn: Callable[[], A]) -> EffectAsync[A]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffectAsync.__name__, 'delay_to_thread')
    return DelayThreadAsync(fn)


def retry(
        fn: Callable[[], Awaitable[A]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[A], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffectAsync[A]:
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
    return RetryAsync(
        thunk=fn,
        total_attempts=total_attempts,
        wait_seconds_on_attempt=wait_seconds_on_attempt,
        pause_seconds_between=pause_seconds_between,
        retry_on_result=retry_on_result,
        retry_on_exceptions=retry_on_exceptions,
        step_name=step_name
    )


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


def pure_t(value: A) -> EffectAsyncT[A, Never]:
    """Wraps a ready-made value"""
    return EffectAsyncT(PureAsync(Ok(value)))


def error_t(error: E) -> EffectAsyncT[Never, E]:
    """Wraps a ready-made error"""
    return EffectAsyncT(PureAsync(Err(error)))


def lift_result_t(result: Result[A, E]) -> EffectAsyncT[A, E]:
    """Wraps a ready-made Result value"""
    return EffectAsyncT(PureAsync(result))


def lift_effect_t(effect: EffectAsync[A]) -> EffectAsyncT[A, Never]:
    """Lift the effect to a transformer"""
    return EffectAsyncT(BindAsync(effect, lambda a: PureAsync(Ok(a))))


def delay_t(
        fn: Callable[[], Awaitable[Result[A, E]]],
        wait_seconds: int | float | None = None
) -> EffectAsyncT[A, E]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution
        :raises ValidationError: incorrect wait_seconds parameter
    """
    return EffectAsyncT(DelayAsync(fn, wait_seconds))


def delay_to_thread_t(fn: Callable[[], Result[A, E]]) -> EffectAsyncT[A, E]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffectAsyncT.__name__, 'delay_to_thread_t')
    return EffectAsyncT(DelayThreadAsync(fn))


def retry_t(
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
