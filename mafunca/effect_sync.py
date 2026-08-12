from __future__ import annotations
from dataclasses import dataclass
import inspect
from collections.abc import Callable
from typing import TypeVar, Generic

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "Effect",
    "pure",
    "delay",
    "retry",
    "lift2",
    "lift3",
    "lift4",
]


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)


class Effect(Generic[A]):
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """

    def map(self, fn: Callable[[A], B]) -> Effect[B]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return Bind(self, lambda a: Pure(fn(a)))

    def bind(self, fn: Callable[[A], Effect[B]]) -> Effect[B]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return Bind(self, fn)

    def catch_map(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Effect[A]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return Catch(self, exc_type, lambda exc: Pure(catcher(exc)))

    def catch_bind(self, exc_type: type[Exc], catcher: Callable[[Exc], Effect[A]]) -> Effect[A]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return Catch(self, exc_type, catcher)

    def ensure(self, finalizer: Effect[None]) -> Effect[A]:
        return Ensure(self, finalizer)


@dataclass(frozen=True, slots=True, repr=True)
class Pure(Generic[A], Effect[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class Delay(Generic[A], Effect[A]):
    thunk: Callable[[], A]


class Retry(Generic[A], Effect[A]):
    __slots__ = (
        "thunk",
        "total_attempts",
        "pause_seconds_between",
        "retry_on_result",
        "retry_on_exceptions",
        "step_name"
    )

    def __init__(
            self,
            thunk: Callable[[], A],
            total_attempts: int,
            pause_seconds_between: Callable[[int], int | float],
            retry_on_result: Callable[[A], bool],
            retry_on_exceptions: tuple[type[Exception], ...],
            step_name: str
    ):
        if not isinstance(total_attempts, int) or total_attempts < 1:
            raise ValidationError("total_attempts must be a positive integer")
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
        self.pause_seconds_between = pause_seconds_between
        self.retry_on_result = retry_on_result
        self.retry_on_exceptions = retry_on_exceptions
        self.step_name = step_name


@dataclass(frozen=True, slots=True, repr=True)
class Bind(Generic[A, B], Effect[B]):
    current: Effect[A]
    continuation: Callable[[A], Effect[B]]


@dataclass(frozen=True, slots=True, repr=True)
class Catch(Generic[A, Exc], Effect[A]):
    current: Effect[A]
    exc_type: type[Exc]
    catcher: Callable[[Exc], Effect[A]]


@dataclass(frozen=True, slots=True, repr=True)
class Ensure(Generic[A], Effect[A]):
    current: Effect[A]
    finalizer: Effect[None]


def pure(value: A) -> Effect[A]:
    """Wraps a ready-made value"""
    return Pure(value)


def delay(fn: Callable[[], A]) -> Effect[A]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Effect.__name__, 'delay')
    return Delay(fn)


def retry(
        fn: Callable[[], A],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[A], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> Effect[A]:
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
    panic_on_coroutine(fn, Effect.__name__, 'retry')
    return Retry(
        thunk=fn,
        total_attempts=total_attempts,
        pause_seconds_between=pause_seconds_between,
        retry_on_result=retry_on_result,
        retry_on_exceptions=retry_on_exceptions,
        step_name=step_name
    )


def _ap(wrapped_fn: Effect[Callable[[A], B]], wrapped_val: Effect[A]) -> Effect[B]:
    return wrapped_fn.bind(lambda fn: wrapped_val.map(lambda val: fn(val)))


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: Effect[A1],
        arg2: Effect[A2]
) -> Effect[B]:
    return _ap(_ap(Pure(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: Effect[A1],
        arg2: Effect[A2],
        arg3: Effect[A3]
) -> Effect[B]:
    return _ap(_ap(_ap(Pure(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: Effect[A1],
        arg2: Effect[A2],
        arg3: Effect[A3],
        arg4: Effect[A4],
) -> Effect[B]:
    return _ap(_ap(_ap(_ap(Pure(curry4(fn)), arg1), arg2), arg3), arg4)
