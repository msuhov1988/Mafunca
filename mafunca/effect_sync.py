from __future__ import annotations
from dataclasses import dataclass
import inspect
from collections.abc import Callable
from typing import TypeVar, Generic, Any

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "Eff",
    "pure",
    "delay",
    "retry",
    "ap",
    "lift2",
    "lift3",
    "lift4",
]


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)


class Eff(Generic[A]):
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """

    def fmap(self, fn: Callable[[A], B]) -> Eff[B]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'fmap')
        return _Bind(self, lambda a: _Pure(fn(a)))

    def bind(self, fn: Callable[[A], Eff[B]]) -> Eff[B]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return _Bind(self, fn)

    def catch_fmap(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> Eff[A]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_fmap')
        return _Catch(self, exc_type, lambda exc: _Pure(catcher(exc)))

    def catch_bind(self, exc_type: type[Exc], catcher: Callable[[Exc], Eff[A]]) -> Eff[A]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return _Catch(self, exc_type, catcher)

    def ensure(self, finalizer: Eff[None]) -> Eff[A]:
        return _Ensure(self, finalizer)


@dataclass(frozen=True, slots=True, repr=True)
class _Pure(Generic[A], Eff[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class _Delay(Generic[A], Eff[A]):
    thunk: Callable[[], A]


class _Retry(Generic[A], Eff[A]):
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
        if total_attempts < 1:
            raise ValidationError("total_attempts must be a positive integer")    
        if not callable(pause_seconds_between) or inspect.iscoroutinefunction(pause_seconds_between):
            raise ValidationError("pause_seconds_between must be a SYNC callable object")
        if not callable(retry_on_result) or inspect.iscoroutinefunction(retry_on_result):
            raise ValidationError("retry_on_result must be a SYNC callable object")        
        self.thunk = thunk
        self.total_attempts = total_attempts
        self.pause_seconds_between = pause_seconds_between
        self.retry_on_result = retry_on_result
        self.retry_on_exceptions = retry_on_exceptions
        self.step_name = step_name


@dataclass(frozen=True, slots=True, repr=True)
class _Bind(Generic[B], Eff[B]):
    current: Eff[Any]
    continuation: Callable[[Any], Eff[B]]


@dataclass(frozen=True, slots=True, repr=True)
class _Catch(Generic[A], Eff[A]):
    current: Eff[A]
    exc_type: Any
    catcher: Callable[[Any], Eff[A]]


@dataclass(frozen=True, slots=True, repr=True)
class _Ensure(Generic[A], Eff[A]):
    current: Eff[A]
    finalizer: Eff[None]


def pure(value: A) -> Eff[A]:
    """Wraps a ready-made value"""
    return _Pure(value)


def delay(fn: Callable[[], A]) -> Eff[A]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Eff.__name__, 'delay')
    return _Delay(fn)


def retry(
        fn: Callable[[], A],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[A], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> Eff[A]:
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
    panic_on_coroutine(fn, Eff.__name__, 'retry')
    return _Retry(
        thunk=fn,
        total_attempts=total_attempts,
        pause_seconds_between=pause_seconds_between,
        retry_on_result=retry_on_result,
        retry_on_exceptions=retry_on_exceptions,
        step_name=step_name
    )


def ap(effect: Eff[A], fn: Eff[Callable[[A], B]]) -> Eff[B]:
    return fn.bind(lambda fn_inner: effect.fmap(lambda val: fn_inner(val)))


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: Eff[A1],
        arg2: Eff[A2]
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift2')
    return ap(arg2, ap(arg1, _Pure(curry2(fn))))


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: Eff[A1],
        arg2: Eff[A2],
        arg3: Eff[A3]
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift3')
    return ap(arg3, ap(arg2, ap(arg1, _Pure(curry3(fn)))))


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: Eff[A1],
        arg2: Eff[A2],
        arg3: Eff[A3],
        arg4: Eff[A4],
) -> Eff[B]:
    """:raises MonadError: coroutine function is not allowed"""
    panic_on_coroutine(fn, Eff.__name__, 'lift4')
    return ap(arg4, ap(arg3, ap(arg2, ap(arg1, _Pure(curry4(fn))))))
