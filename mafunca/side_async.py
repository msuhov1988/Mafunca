from dataclasses import dataclass
import asyncio
from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, Any, Union, Optional, cast

from mafunca._lazy_support import continuation_catch  # noqa
from mafunca._lazy_support import async_prime_catch, async_prime_thread_catch  # noqa
from mafunca._lazy_support import panic_on_violations, panic_on_coroutine  # noqa
from mafunca.result import Result, Ok, Err
from mafunca.side_report import Report


__all__ = [
    "AsyncSide",
    "async_side_run",
    "async_side_safe_run",
    "async_side_rebuild_run",
    "async_insist"
]


A = TypeVar("A")
B = TypeVar("B")


class AsyncSide(Generic[A]):
    """
        A monad for asynchronous effects.
        Lazy: not executed until the corresponding executor is called.
    """

    def map(self, fn: Callable[[A], B]) -> 'AsyncSide[B]':
        """
            Only for synchronous functions - pure calculation
            :raises MonadError: function must be sync
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return AsyncContinuation(self, lambda a: AsyncPure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'AsyncSide[B]']) -> 'AsyncSide[B]':
        """
            The function that returns the effect must be synchronous.
            Asynchrony is assumed inside the effect
            :raises MonadError: function must be sync
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return AsyncContinuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'AsyncSide[A]':
        return AsyncPure(value)

    @staticmethod
    def effect(fn: Callable[[], Awaitable[A]], delay: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        return AsyncPrime(fn, delay)

    @staticmethod
    def effect_to_thread(fn: Callable[[], A], delay: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        """
            Only for synchronous functions - will be executed in a separate thread
            :raises MonadError: function must be sync
        """
        panic_on_coroutine(fn, AsyncSide.__name__, 'effect_to_thread')
        return AsyncPrimeThread(fn, delay)


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPure(AsyncSide[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPrime(AsyncSide[A]):
    prime: Callable[[], Awaitable[A]]
    delay: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPrimeThread(AsyncSide[A]):
    prime_thread: Callable[[], A]
    delay: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class AsyncContinuation(AsyncSide[B]):
    current: AsyncSide[Any]
    next: Callable[[Any], AsyncSide[B]]
    next_origin: Callable[[Any], Union[B, AsyncSide[B]]]


async def async_side_run(effect: AsyncSide[A]) -> A:
    """
        Simple asynchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
        :raises TimeoutError: delay is set for the effect and the waiting time has been exceeded.
    """
    entity, continuations = effect, list()
    while True:
        if isinstance(entity, AsyncContinuation):
            continuations.append(entity.next)
            entity = entity.current

        elif isinstance(entity, AsyncPrime):
            if entity.delay is None:
                output = await entity.prime()
            else:
                async with asyncio.timeout(delay=entity.delay):
                    output = await entity.prime()
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPrimeThread):
            if entity.delay is None:
                output = await asyncio.to_thread(entity.prime_thread)
            else:
                async with asyncio.timeout(delay=entity.delay):
                    output = await asyncio.to_thread(entity.prime_thread)
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPure):
            if len(continuations) == 0:
                return cast(A, entity.value)
            cont = continuations.pop()
            entity = cont(entity.value)

        else:
            panic_on_violations(AsyncSide.__name__, 'async_side_run', entity)


async def async_side_safe_run(effect: AsyncSide[A]) -> Result[A, Exception]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
        :raises TimeoutError: delay is set for the effect and the waiting time has been exceeded.
    """
    entity, continuations = effect, list()
    while True:
        if isinstance(entity, AsyncContinuation):
            continuations.append(entity.next)
            entity = entity.current

        elif isinstance(entity, AsyncPrime):
            result = await async_prime_catch(entity.prime, delay=entity.delay)
            if isinstance(result, Err):
                return cast(Result[A, Exception], result)
            entity = AsyncPure(result.value)

        elif isinstance(entity, AsyncPrimeThread):
            result = await async_prime_thread_catch(entity.prime_thread, delay=entity.delay)
            if isinstance(result, Err):
                return cast(Result[A, Exception], result)
            entity = AsyncPure(result.value)

        elif isinstance(entity, AsyncPure):
            if len(continuations) == 0:
                return cast(Result[A, Exception], Ok(entity.value))
            cont = continuations.pop()
            result = continuation_catch(cont, entity.value)
            if isinstance(result, Err):
                return cast(Result[A, Exception], result)
            entity = result.value

        else:
            panic_on_violations(AsyncSide.__name__, 'async_side_safe_run', entity)


def _rebuild_from_prime(prime, delay, continuations, to_thread: bool) -> AsyncSide:
    effect = AsyncSide.effect(prime, delay) if not to_thread else AsyncSide.effect_to_thread(prime, delay)

    while len(continuations) > 0:
        cont, cont_origin = continuations.pop()
        effect = AsyncContinuation(effect, cont, cont_origin)

    return effect


def _rebuild_from_pure(pure_val, continuations) -> AsyncSide:
    effect = AsyncSide.pure(pure_val)

    while len(continuations) > 0:
        cont, cont_origin = continuations.pop()
        effect = AsyncContinuation(effect, cont, cont_origin)

    return effect


async def async_side_rebuild_run(effect: AsyncSide[A]) -> Report[Any, AsyncSide[A]]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
        :raises TimeoutError: delay is set for the effect and the waiting time has been exceeded.
    """
    entity, continuations, last_success = effect, list(), None
    while True:
        if isinstance(entity, AsyncContinuation):
            continuations.append((entity.next, entity.next_origin))
            entity = entity.current

        elif isinstance(entity, AsyncPrime):
            result = await async_prime_catch(entity.prime, delay=entity.delay)
            if isinstance(result, Err):
                rest = _rebuild_from_prime(entity.prime, entity.delay, continuations, to_thread=False)
                return cast(
                    Report[Any, AsyncSide[A]],
                    Report(last_success, result.error, entity.prime, remainder=rest)
                )
            entity = AsyncPure(result.value)

        elif isinstance(entity, AsyncPrimeThread):
            result = await async_prime_thread_catch(entity.prime_thread, delay=entity.delay)
            if isinstance(result, Err):
                rest = _rebuild_from_prime(entity.prime_thread, entity.delay, continuations, to_thread=True)
                return cast(
                    Report[Any, AsyncSide[A]],
                    Report(last_success, result.error, entity.prime_thread, remainder=rest)
                )
            entity = AsyncPure(result.value)

        elif isinstance(entity, AsyncPure):
            if len(continuations) == 0:
                return cast(Report[Any, AsyncSide[A]], Report(entity.value, None, None, remainder=None))
            last_success = entity.value
            cont, cont_origin = continuations.pop()
            result = continuation_catch(cont, last_success)
            if isinstance(result, Err):
                continuations.append((cont, cont_origin))
                rest = _rebuild_from_pure(last_success, continuations)
                return cast(Report[Any, AsyncSide[A]], Report(last_success, result.error, cont_origin, remainder=rest))
            entity = result.value

        else:
            panic_on_violations(AsyncSide.__name__, 'async_side_rebuild_run', entity)


async def async_insist(
        effect: AsyncSide[A],
        attempts: int = 1,
        pause: Union[int, float] = 0
) -> Report[Any, AsyncSide[A]]:
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
        :raises TimeoutError: delay is set for the effect and the waiting time has been exceeded.
    """
    chain, report = effect, Report(None, None, None, effect)
    for _ in range(attempts):
        report = await async_side_rebuild_run(chain)
        if not report.completed_successfully:
            chain = report.remainder
            await asyncio.sleep(pause)
            continue
        break
    return cast(Report[Any, AsyncSide[A]], report)
