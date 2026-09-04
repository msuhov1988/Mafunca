from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeVar, Generic, Never, cast

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err
from mafunca.effect_sync import Effect
from mafunca.effect_sync import Pure, Delay, Retry  # noqa
from mafunca.effect_sync import Bind, Catch, Ensure  # noqa
from mafunca.curry import curry2, curry3, curry4


__all__ = [
    "EffectResult",
    "pure",
    "lift_error",
    "lift_result",
    "lift_effect",
    "delay",
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
class EffectResult(Generic[A, E]):
    """
        A transformer for SYNCHRONOUS ONLY effects.

        Container for a composite value of the form 'EffectSync[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: Effect[Result[A, E]]

    def map(self, fn: Callable[[A], B]) -> EffectResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return EffectResult(Bind(self.inner, lambda res: Pure(res.map(fn))))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> EffectResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return EffectResult(Bind(self.inner, lambda res: Pure(res.bind(fn))))

    def map_error(self, fn: Callable[[E], NewE]) -> EffectResult[A, NewE]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_error')
        return EffectResult(Bind(self.inner, lambda res: Pure(res.map_error(fn))))

    def bind(self, fn: Callable[[A], EffectResult[B, E]]) -> EffectResult[B, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> Effect[Result[B, E]]:
            if isinstance(arg, Err):
                return Pure(arg)
            return fn(arg.value).inner

        return EffectResult(Bind(self.inner, continuation))

    def catch_map(self, exc_type: type[Exc], catcher: Callable[[Exc], A]) -> EffectResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map')
        return EffectResult(Catch(self.inner, exc_type, lambda exc: Pure(Ok(catcher(exc)))))

    def catch_map_result(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], Result[A, E]]
    ) -> EffectResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_map_result')
        return EffectResult(Catch(self.inner, exc_type, lambda exc: Pure(catcher(exc))))

    def catch_bind(
            self,
            exc_type: type[Exc],
            catcher: Callable[[Exc], EffectResult[A, E]]
    ) -> EffectResult[A, E]:
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(catcher, self.__class__.__name__, 'catch_bind')
        return EffectResult(Catch(self.inner, exc_type, lambda exc: catcher(exc).inner))

    def ensure(self, finalizer: Effect[None]) -> EffectResult[A, E]:
        return EffectResult(Ensure(self.inner, finalizer))


def pure(value: A) -> EffectResult[A, Never]:
    """Wraps a ready-made value"""
    return EffectResult(Pure(Ok(value)))


def lift_error(err: E) -> EffectResult[Never, E]:
    """Wraps a ready-made error"""
    return EffectResult(Pure(Err(err)))


def lift_result(result: Result[A, E]) -> EffectResult[A, E]:
    """Wraps a ready-made Result value"""
    return EffectResult(Pure(result))


def lift_effect(effect: Effect[A]) -> EffectResult[A, Never]:
    """Lift the effect to a transformer"""
    return EffectResult(Bind(effect, lambda a: Pure(Ok(a))))


def delay(fn: Callable[[], Result[A, E]]) -> EffectResult[A, E]:
    """
        Wraps a SYNCHRONOUS function for delayed execution.
        :raises MonadError: coroutine functions are not allowed
    """
    panic_on_coroutine(fn, EffectResult.__name__, 'delay')
    return EffectResult(Delay(fn))


def retry(
        fn: Callable[[], Result[A, E]],
        *,
        total_attempts: int = 1,
        pause_seconds_between: Callable[[int], int | float] = lambda _: 0,
        retry_on_result: Callable[[Result[A, E]], bool] = lambda _: False,
        retry_on_exceptions: tuple[type[Exception], ...] = (),
        step_name: str = '',
) -> EffectResult[A, E]:
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
    panic_on_coroutine(fn, EffectResult.__name__, 'retry')
    return EffectResult(
        Retry(
            thunk=fn,
            total_attempts=total_attempts,
            pause_seconds_between=pause_seconds_between,
            retry_on_result=retry_on_result,
            retry_on_exceptions=retry_on_exceptions,
            step_name=step_name
        )
    )


A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def _ap(wrapped_fn: EffectResult[Callable[[A], B], E], wrapped_val: EffectResult[A, E]) -> EffectResult[B, E]:
    return wrapped_fn.bind(lambda fn: wrapped_val.map(lambda val: fn(val)))


def lift2(
        fn: Callable[[A1, A2], B],
        arg1: EffectResult[A1, E],
        arg2: EffectResult[A2, E]
) -> EffectResult[B, E]:
    return cast(EffectResult[B, E], _ap(_ap(pure(curry2(fn)), arg1), arg2))


def lift3(
        fn: Callable[[A1, A2, A3], B],
        arg1: EffectResult[A1, E],
        arg2: EffectResult[A2, E],
        arg3: EffectResult[A3, E]
) -> EffectResult[B, E]:
    return cast(EffectResult[B, E], _ap(_ap(_ap(pure(curry3(fn)), arg1), arg2), arg3))


def lift4(
        fn: Callable[[A1, A2, A3, A4], B],
        arg1: EffectResult[A1, E],
        arg2: EffectResult[A2, E],
        arg3: EffectResult[A3, E],
        arg4: EffectResult[A4, E],
) -> EffectResult[B, E]:
    return cast(EffectResult[B, E], _ap(_ap(_ap(_ap(pure(curry4(fn)), arg1), arg2), arg3), arg4))
