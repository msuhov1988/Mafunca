from dataclasses import dataclass
import asyncio
from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, Any, Union, Optional, cast

from mafunca.common._lazy_support import prime_catch, continuation_catch  # noqa
from mafunca.common._lazy_support import async_prime_catch, async_prime_thread_catch  # noqa
from mafunca.common._lazy_support import panic_on_violations, panic_on_coroutine  # noqa
from mafunca.result import Result, Ok, Err
from mafunca.common.side_support import Report


__all__ = [
    "AsyncSide",
    "side_run",
    "side_safe_run",
    "side_rebuild_run",
    "insist"
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
        panic_on_coroutine(fn, AsyncSide.__name__, 'prime_to_thread')
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


async def side_run(effect: AsyncSide[A]) -> A:
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
            panic_on_violations(AsyncSide.__name__, 'side_run', entity)


async def side_safe_run(effect: AsyncSide[A]) -> Result[A, Exception]:
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
            output, error = await async_prime_catch(entity.prime, delay=entity.delay)
            if error is not None:
                return cast(Result[A, Exception], Err(error))
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPrimeThread):
            output, error = await async_prime_thread_catch(entity.prime_thread, delay=entity.delay)
            if error is not None:
                return cast(Result[A, Exception], Err(error))
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPure):
            if len(continuations) == 0:
                return cast(Result[A, Exception], Ok(entity.value))
            cont = continuations.pop()
            output, error = continuation_catch(cont, entity.value)
            if error is not None:
                return cast(Result[A, Exception], Err(error))
            entity = output

        else:
            panic_on_violations(AsyncSide.__name__, 'side_safe_run', entity)


def _rebuild_from_prime(prime, continuations, to_thread: False) -> AsyncSide:
    effect = AsyncSide.effect(prime) if not to_thread else AsyncSide.effect_to_thread(prime)

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


async def side_rebuild_run(effect: AsyncSide[A]) -> Report[AsyncSide[A]]:
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
            output, error = await async_prime_catch(entity.prime, delay=entity.delay)
            if error is not None:
                rest = _rebuild_from_prime(entity.prime, continuations, to_thread=False)
                return cast(Report[AsyncSide[A]], Report(last_success, error, entity.prime, remainder=rest))
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPrimeThread):
            output, error = await async_prime_thread_catch(entity.prime_thread, delay=entity.delay)
            if error is not None:
                rest = _rebuild_from_prime(entity.prime_thread, continuations, to_thread=True)
                return cast(Report[AsyncSide[A]], Report(last_success, error, entity.prime_thread, remainder=rest))
            entity = AsyncPure(output)

        elif isinstance(entity, AsyncPure):
            if len(continuations) == 0:
                return cast(Report[AsyncSide[A]], Report(entity.value, None, faulty=None, remainder=None))
            last_success = entity.value
            cont, cont_origin = continuations.pop()
            output, error = continuation_catch(cont, last_success)
            if error is not None:
                continuations.append((cont, cont_origin))
                rest = _rebuild_from_pure(last_success, continuations)
                return cast(Report[AsyncSide[A]], Report(last_success, error, faulty=cont_origin, remainder=rest))
            entity = output

        else:
            panic_on_violations(AsyncSide.__name__, 'side_rebuild_run', entity)


async def insist(effect: AsyncSide[A], attempts: int = 1, pause: Union[int, float] = 0) -> Report[AsyncSide[A]]:
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
        :raises TimeoutError: delay is set for the effect and the waiting time has been exceeded.
    """
    chain, report = effect, Report(None, None, None, None)
    for _ in range(attempts):
        report = await side_rebuild_run(chain)
        if not report.completed_successfully:
            chain = report.remainder
            await asyncio.sleep(pause)
            continue
        break
    return cast(Report[AsyncSide[A]], report)
