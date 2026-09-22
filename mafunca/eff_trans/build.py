from collections.abc import Callable
from typing import TypeVar, TypeAlias, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result.build import Result, Success, Fail
from mafunca.eff.build import Eff
from mafunca.eff.build import _Pure, _Delay, _Retry, _Bind, _Bracket  # type: ignore # noqa


__all__ = [
    "EffResult",
    "pure_success",
    "pure_fail",
    "pure_result",
    "lift_effect",    
    "delay",
    "retry",
]


A = TypeVar("A")
E = TypeVar("E")
Enew = TypeVar('Enew')


EffResult: TypeAlias = Eff[Result[A, E]]


S = TypeVar("S")
F = TypeVar("F")
R = TypeVar("R")


def pure_success(value: S) -> EffResult[S, Never]:
    """Wraps a ready-made value"""
    return _Pure(Success(value))


def pure_fail(err: F) -> EffResult[Never, F]:
    """Wraps a ready-made error"""
    return _Pure(Fail(err))


def pure_result(result: Result[S, F]) -> EffResult[S, F]:
    """Wraps a ready-made Result value"""
    return _Pure(result)


def lift_effect(effect: Eff[S]) -> EffResult[S, Never]:
    """Lift the effect to a transformer"""
    return _Bind(effect, lambda a: _Pure(Success(a)))


def delay(fn: Callable[[], Result[S, F]]) -> EffResult[S, F]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.

        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffResult.__name__, 'delay')
    return _Delay(fn)


def retry(
        fn: Callable[[], Result[S, F]],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[S, F]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffResult[S, F]:
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
    panic_on_coroutine(fn, EffResult.__name__, 'retry')
    return _Retry(
        thunk=fn,
        total_attempts=total_attempts,
        pause_seconds_between=pause_seconds_between,
        retry_on_result=retry_on_result,
        retry_on_exceptions=retry_on_exceptions,
        step_name=step_name
    )
