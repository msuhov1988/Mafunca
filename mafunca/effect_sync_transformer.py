from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, Generic, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err
from mafunca.effect_sync import EffectSync
from mafunca.effect_sync import Pure, Delay, Retry  # noqa
from mafunca.effect_sync import Bind, Catch, Ensure  # noqa


__all__ = [
    "EffectSyncT",
    "pure",
    "lift_error",
    "lift_result",
    "lift_effect",
    "delay",
    "retry"
]


A = TypeVar("A")
B = TypeVar("B")
Exc = TypeVar("Exc", bound=Exception)
E = TypeVar("E")
NewE = TypeVar('NewE')


@dataclass(frozen=True, slots=True, repr=True)
class EffectSyncT(Generic[A, E]):
    """
        A transformer for SYNCHRONOUS ONLY effects.

        Container for a composite value of the form 'EffectSync[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: EffectSync[Result[A, E]]

    def map(self, fn: Callable[[A], B]) -> EffectSyncT[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return EffectSyncT(Bind(self.inner, lambda res: Pure(res.map(fn))))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> EffectSyncT[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return EffectSyncT(Bind(self.inner, lambda res: Pure(res.bind(fn))))

    def map_error(self, fn: Callable[[E], NewE]) -> EffectSyncT[A, NewE]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_error')
        return EffectSyncT(Bind(self.inner, lambda res: Pure(res.map_error(fn))))

    def bind(self, fn: Callable[[A], EffectSyncT[B, E]]) -> EffectSyncT[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> EffectSync[Result[B, E]]:
            if isinstance(arg, Err):
                return Pure(arg)
            return fn(arg.value).inner

        return EffectSyncT(Bind(self.inner, continuation))

    def catch_map(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> EffectSyncT[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return EffectSyncT(Catch(self.inner, exc_type, lambda exc: Pure(Ok(catcher(exc)))))

    def catch_map_result(self, exc_type: type[Exc], catcher: Callable[[Exc], Result[A, E]]) -> EffectSyncT[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map_result')
        return EffectSyncT(Catch(self.inner, exc_type, lambda exc: Pure(catcher(exc))))

    def catch_bind(self, exc_type: type[Exc], catcher: Callable[[Exc], EffectSyncT[A, E]]) -> EffectSyncT[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return EffectSyncT(Catch(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: EffectSync[None]) -> EffectSyncT[A, E]:
        return EffectSyncT(Ensure(self.inner, finalizer))


def pure(value: A) -> EffectSyncT[A, Never]:
    """Wraps a ready-made value"""
    return EffectSyncT(Pure(Ok(value)))


def lift_error(err: E) -> EffectSyncT[Never, E]:
    """Wraps a ready-made error"""
    return EffectSyncT(Pure(Err(err)))


def lift_result(result: Result[A, E]) -> EffectSyncT[A, E]:
    """Wraps a ready-made Result value"""
    return EffectSyncT(Pure(result))


def lift_effect(effect: EffectSync[A]) -> EffectSyncT[A, Never]:
    """Lift the effect to a transformer"""
    return EffectSyncT(Bind(effect, lambda a: Pure(Ok(a))))


def delay(fn: Callable[[], Result[A, E]]) -> EffectSyncT[A, E]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffectSyncT.__name__, 'delay')
    return EffectSyncT(Delay(fn))


def retry(
        fn: Callable[[], Result[A, E]],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[A, E]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffectSyncT[A, E]:
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
    panic_on_coroutine(fn, EffectSyncT.__name__, 'retry')
    return EffectSyncT(
        Retry(
            thunk=fn,
            total_attempts=total_attempts,
            pause_seconds_between=pause_seconds_between,
            retry_on_result=retry_on_result,
            retry_on_exceptions=retry_on_exceptions,
            step_name=step_name
        )
    )
