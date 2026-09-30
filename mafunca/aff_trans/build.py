from dataclasses import dataclass
from collections.abc import Callable, Awaitable, Generator
from typing import TypeVar, Generic, ParamSpec, Never, Any


from mafunca._lazy_support import panic_on_coroutine, ShortCircuitedError
from mafunca.result.build import Result, Success, Fail
from mafunca.aff.build import Aff
from mafunca.aff.build import _PureAsync, _DelayAsync, _DelayThreadAsync, _RetryAsync, _BindAsync  # type: ignore # noqa


__all__ = [
    "AffResult",
    "pure_success",
    "pure_fail",
    "pure_result",
    "lift_effect",
    "delay",
    "delay_to_thread",
    "retry",
    "Do",
    "AffResultGenBased",
    "Step",
    "step",
    "do",
]

A = TypeVar("A", covariant=True)
E = TypeVar("E", covariant=True)


type AffResult[A, E] = Aff[Result[A, E]]    


S = TypeVar("S")
F = TypeVar("F")
R = TypeVar("R")
Args = ParamSpec('Args')


def pure_success(value: S) -> AffResult[S, Never]:
    """Wraps a ready-made value"""
    return _PureAsync(Success(value))


def pure_fail(error: F) -> AffResult[Never, F]:
    """Wraps a ready-made error"""
    return _PureAsync(Fail(error))


def pure_result(result: Result[S, F]) -> AffResult[S, F]:
    """Wraps a ready-made Result value"""
    return _PureAsync(result)


def lift_effect(effect: Aff[S]) -> AffResult[S, Never]:
    """Lift the effect to a transformer"""
    return _BindAsync(effect, lambda a: _PureAsync(Success(a)))


def delay(
        fn: Callable[[], Awaitable[Result[S, F]]],
        wait_seconds: int | float | None = None
) -> AffResult[S, F]:
    """
        Wraps an ASYNCHRONOUS function for delayed execution

        :raises ValidationError: incorrect wait_seconds parameter
    """
    return _DelayAsync(fn, wait_seconds)


def delay_to_thread(fn: Callable[[], Result[S, F]]) -> AffResult[S, F]:
    """
        Wraps a SYNCHRONOUS function for delayed execution in a separate thread

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, AffResult.__name__, 'delay_to_thread')
    return _DelayThreadAsync(fn)


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
type Do[A, E] = Generator[AffResult[Any, E], Any, A]


@dataclass(frozen=True, slots=True)
class AffResultGenBased(Generic[A, E]):
    """
        A monad over ``Result`` for ASYNCHRONOUS effects, presented as a generator workflow
    """
    workflow: Callable[[], Do[A, E]]

    def __iter__(self) -> Do[A, E]:
        gen = None        
        try:
            gen = self.workflow()             
            return (yield from gen)
        finally:
            if gen is not None:            
                gen.close()


@dataclass(frozen=True, slots=True)
class Step(Generic[A, E]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: AffResult[A, E] | AffResultGenBased[A, E]

    def __iter__(self) -> Generator[AffResult[A, E], Result[A, E], A]:
        if isinstance(self.for_yield, Aff):       
            result = yield self.for_yield
            if isinstance(result, Success):
                return result.value       
            raise ShortCircuitedError(result) 
        
        return (yield from self.for_yield) 


def step(for_yield: AffResult[A, E] | AffResultGenBased[A, E]) -> Step[A, E]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


def do(workflow: Callable[Args, Do[A, E]]) -> Callable[Args, AffResultGenBased[A, E]]:
    """
        Decorates a generator function implementing an ``AffResult`` computations.

        The internal wrapper function does not perform any calculations; it returns an ``AffResultGenBased`` object
    """ 

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> AffResultGenBased[A, E]:   
        return AffResultGenBased(lambda: workflow(*args, **kwargs))

    return do_inner
