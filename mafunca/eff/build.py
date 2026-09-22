from dataclasses import dataclass
import inspect
from collections.abc import Callable
from typing import TypeVar, Generic

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine


__all__ = [
    "Eff",
    "pure",
    "delay",
    "retry",
]


A_co = TypeVar("A_co", covariant=True)
A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
Exc = TypeVar("Exc", bound=Exception)


class Eff(Generic[A_co]):
    __slots__ = ()
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """ 
    pass   


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
class _Bind(Generic[A, B], Eff[B]):
    current: Eff[A]
    continuation: Callable[[A], Eff[B]]


@dataclass(frozen=True, slots=True, repr=True)
class _Catch(Generic[A, Exc], Eff[A]):
    current: Eff[A]
    exc_type: type[Exc]
    catcher: Callable[[Exc], Eff[A]]


@dataclass(frozen=True, slots=True, repr=True)
class _Ensure(Generic[A, B], Eff[A]):
    current: Eff[A]
    finalizer: Eff[B]


@dataclass(frozen=True, slots=True, repr=True)
class _Bracket(Generic[A, B, C], Eff[B]):
    acquire: Eff[A]
    use: Callable[[A], Eff[B]]
    release: Callable[[A], Eff[C]]


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


def bracket(
        acquire: Eff[A], 
        use: Callable[[A], Eff[B]], 
        release: Callable[[A], Eff[None]]
) -> Eff[B]:
    return _Bracket(acquire, use, release)
