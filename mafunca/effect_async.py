from __future__ import annotations
from dataclasses import dataclass
import inspect
from collections.abc import Callable, Awaitable
from typing import TypeVar, Generic

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "Aff",
    "pure",
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


class Aff(Generic[A]):
    """
        A monad for ASYNCHRONOUS effects.
        Lazy: not executed until the corresponding executor is called.
    """

    def map(self, fn: Callable[[A], B]) -> Aff[B]:
        """
            Only for SYNCHRONOUS functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return BindAsync(self, lambda a: PureAsync(fn(a)))

    def bind(self, fn: Callable[[A], Aff[B]]) -> Aff[B]:
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
    ) -> Aff[A]:
        """
            Only for SYNCHRONOUS catchers - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return CatchAsync(self, exc_type, lambda exc: PureAsync(catcher(exc)))

    def catch_bind(
            self,
            exc_type: type[Exc] | type[TimeoutError],
            catcher: Callable[[Exc | TimeoutError], Aff[A]]
    ) -> Aff[A]:
        """
            The catcher that returns the effect must be SYNCHRONOUS.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return CatchAsync(self, exc_type, catcher)

    def ensure(self, finalizer: Aff[None]) -> Aff[A]:
        return EnsureAsync(self, finalizer)


@dataclass(frozen=True, slots=True, repr=True)
class PureAsync(Generic[A], Aff[A]):
    value: A


class DelayAsync(Generic[A], Aff[A]):
    __slots__ = ('thunk', 'wait_seconds')

    def __init__(
            self,
            thunk: Callable[[], Awaitable[A]],
            wait_seconds: int | float | None
    ):
        if wait_seconds is not None:
            if not isinstance(wait_seconds, (int, float)) or wait_seconds < 0:
                raise ValidationError("wait_seconds must be a non-negative number")
        self.thunk = thunk
        self.wait_seconds = wait_seconds


@dataclass(frozen=True, slots=True, repr=True)
class DelayThreadAsync(Generic[A], Aff[A]):
    thunk: Callable[[], A]


class RetryAsync(Generic[A], Aff[A]):
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
            retry_on_exceptions: tuple[type[Exception | TimeoutError], ...],
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
class BindAsync(Generic[A, B], Aff[B]):
    current: Aff[A]
    continuation: Callable[[A], Aff[B]]


@dataclass(frozen=True, slots=True, repr=True)
class CatchAsync(Generic[A, E], Aff[A]):
    current: Aff[A]
    exc_type: type[E]
    catcher: Callable[[E], Aff[A]]


@dataclass(frozen=True, slots=True, repr=True)
class EnsureAsync(Generic[A], Aff[A]):
    current: Aff[A]
    finalizer: Aff[None]


def pure(value: A) -> Aff[A]:
    """Wraps a ready-made value"""
    return PureAsync(value)


def delay(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None = None
) -> Aff[A]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution
        :raises ValidationError: incorrect wait_seconds parameter
    """
    return DelayAsync(fn, wait_seconds)


def delay_to_thread(fn: Callable[[], A]) -> Aff[A]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Aff.__name__, 'delay_to_thread')
    return DelayThreadAsync(fn)


def retry(
        fn: Callable[[], Awaitable[A]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[A], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception | TimeoutError], ...] = (),
        step_name: str = '',
) -> Aff[A]:
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


def _ap(wrapped_fn: Aff[Callable[[A], B]], wrapped_val: Aff[A]) -> Aff[B]:
    return wrapped_fn.bind(lambda fn: wrapped_val.map(lambda val: fn(val)))


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: Aff[A1],
        arg2: Aff[A2]
) -> Aff[B]:
    return _ap(_ap(PureAsync(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: Aff[A1],
        arg2: Aff[A2],
        arg3: Aff[A3]
) -> Aff[B]:
    return _ap(_ap(_ap(PureAsync(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: Aff[A1],
        arg2: Aff[A2],
        arg3: Aff[A3],
        arg4: Aff[A4],
) -> Aff[B]:
    return _ap(_ap(_ap(_ap(PureAsync(curry4(fn)), arg1), arg2), arg3), arg4)
