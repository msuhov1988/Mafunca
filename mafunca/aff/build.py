from dataclasses import dataclass
import inspect
from collections.abc import Callable, Awaitable, Generator
from typing import TypeVar, Generic, ParamSpec, Any

from mafunca.common.exceptions import ValidationError
from mafunca._lazy_support import panic_on_coroutine


__all__ = [
    "Aff",
    "pure",
    "delay",
    "delay_to_thread",
    "retry",
    "Do",
    "AffGenBased",
    "Step",
    "step",
    "do",
]


A_co = TypeVar("A_co", covariant=True)
A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
Exc = TypeVar("Exc", bound=BaseException)
Args = ParamSpec('Args')


class Aff(Generic[A_co]):   
    """
        A monad for ASYNCHRONOUS effects.
        Lazy: not executed until the corresponding executor is called.
    """
    __slots__ = ()   


@dataclass(frozen=True, slots=True)
class _PureAsync(Generic[A], Aff[A]):
    value: A


class _DelayAsync(Generic[A], Aff[A]):
    __slots__ = ('thunk', 'wait_seconds')

    def __init__(
            self,
            thunk: Callable[[], Awaitable[A]],
            wait_seconds: int | float | None
    ):
        if wait_seconds is not None:
            if wait_seconds < 0:
                raise ValidationError("wait_seconds must be a non-negative number")
        self.thunk = thunk
        self.wait_seconds = wait_seconds


@dataclass(frozen=True, slots=True)
class _DelayThreadAsync(Generic[A], Aff[A]):
    thunk: Callable[[], A]


class _RetryAsync(Generic[A], Aff[A]):
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
        if total_attempts < 1:
            raise ValidationError("total_attempts must be a positive integer")
        if wait_seconds_on_attempt is not None and wait_seconds_on_attempt <= 0:            
            raise ValidationError("wait_seconds_on_attempt must be a positive number")
        if not callable(pause_seconds_between) or inspect.iscoroutinefunction(pause_seconds_between):
            raise ValidationError("pause_seconds_between must be a SYNC callable object")
        if not callable(retry_on_result) or inspect.iscoroutinefunction(retry_on_result):
            raise ValidationError("retry_on_result must be a SYNC callable object")       
        self.thunk = thunk
        self.total_attempts = total_attempts
        self.wait_seconds_on_attempt = wait_seconds_on_attempt
        self.pause_seconds_between = pause_seconds_between
        self.retry_on_result = retry_on_result
        self.retry_on_exceptions = retry_on_exceptions
        self.step_name = step_name


@dataclass(frozen=True, slots=True)
class _BindAsync(Generic[A, B], Aff[B]):
    current: Aff[A]
    continuation: Callable[[A], Aff[B]]


@dataclass(frozen=True, slots=True)
class _CatchAsync(Generic[A, Exc], Aff[A]):
    current: Aff[A]
    exc_type: type[Exc]
    catcher: Callable[[Exc], Aff[A]]


@dataclass(frozen=True, slots=True)
class _EnsureAsync(Generic[A, B], Aff[A]):
    current: Aff[A]
    finalizer: Aff[B]


@dataclass(frozen=True, slots=True)
class _BracketAsync(Generic[A, B, C], Aff[B]):
    acquire: Aff[A]
    use: Callable[[A], Aff[B]]
    release: Callable[[A], Aff[C]]


def pure(value: A) -> Aff[A]:
    """Wraps a ready-made value"""
    return _PureAsync(value)


def delay(
        fn: Callable[[], Awaitable[A]],
        wait_seconds: int | float | None = None
) -> Aff[A]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution

        :raises ValidationError: incorrect wait_seconds parameter
    """
    return _DelayAsync(fn, wait_seconds)


def delay_to_thread(fn: Callable[[], A]) -> Aff[A]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, Aff.__name__, 'delay_to_thread')
    return _DelayThreadAsync(fn)


def retry(
        fn: Callable[[], Awaitable[A]],
        *,
        total_attempts: int = 1,
        wait_seconds_on_attempt: int | float | None = None,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[A], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
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
    return _RetryAsync(
        thunk=fn,
        total_attempts=total_attempts,
        wait_seconds_on_attempt=wait_seconds_on_attempt,
        pause_seconds_between=pause_seconds_between,
        retry_on_result=retry_on_result,
        retry_on_exceptions=retry_on_exceptions,
        step_name=step_name
    )


# a shorter typealias containing all the essential details
# because the types of intermediate results are derived from r = yield from Step(...)
type Do[A] = Generator[Aff[Any], Any, A]


@dataclass(frozen=True, slots=True)
class AffGenBased(Generic[A]):
    """
        A monad for ASYNCHRONOUS effects, presented as a generator workflow
    """
    workflow: Callable[[], Do[A]]

    def __iter__(self) -> Do[A]:
        gen = None        
        try:
            gen = self.workflow()             
            return (yield from gen)
        finally:
            if gen is not None:            
                gen.close()


@dataclass(frozen=True, slots=True)
class Step(Generic[A]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: Aff[A] | AffGenBased[A]

    def __iter__(self) -> Generator[Aff[A], A, A]:
        if isinstance(self.for_yield, Aff):       
            return (yield self.for_yield) 
        return (yield from self.for_yield) 


def step(for_yield: Aff[A] | AffGenBased[A]) -> Step[A]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


def do(workflow: Callable[Args, Do[A]]) -> Callable[Args, AffGenBased[A]]:
    """
        Decorates a generator function implementing an ``Aff`` computations.

        The internal wrapper function does not perform any calculations; it returns an ``AffGenBased`` object
    """ 

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> AffGenBased[A]:   
        return AffGenBased(lambda: workflow(*args, **kwargs))

    return do_inner
