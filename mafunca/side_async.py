from dataclasses import dataclass
import asyncio
from contextlib import closing
from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, Any, Union, Optional, cast

from mafunca.common.exceptions import MonadError
from mafunca._lazy_support import panic_on_violations, panic_on_coroutine  # noqa
from mafunca._lazy_support import runner, rebuild_runner, Yield, Return  # noqa
from mafunca.result import Result, Ok, Err
from mafunca.side_report import Report


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
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return AsyncContinuation(self, lambda a: AsyncPure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'AsyncSide[B]']) -> 'AsyncSide[B]':
        """
            The function that returns the effect must be synchronous.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return AsyncContinuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'AsyncSide[A]':
        return AsyncPure(value)

    @staticmethod
    def effect(fn: Callable[[], Awaitable[A]], timeout: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        return AsyncPrime(fn, timeout)

    @staticmethod
    def effect_to_thread(fn: Callable[[], A], timeout: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        """
            Only for synchronous functions - will be executed in a separate thread
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, AsyncSide.__name__, 'effect_to_thread')
        return AsyncPrimeThread(fn, timeout)


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPure(AsyncSide[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPrime(AsyncSide[A]):
    prime: Callable[[], Awaitable[A]]
    timeout: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class AsyncPrimeThread(AsyncSide[A]):
    prime_thread: Callable[[], A]
    timeout: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class AsyncContinuation(AsyncSide[B]):
    current: AsyncSide[Any]
    next: Callable[[Any], AsyncSide[B]]
    next_origin: Callable[[Any], Union[B, AsyncSide[B]]]


async def _prime_exec(effect, timeout, to_thread):
    coro = asyncio.to_thread(effect) if to_thread else effect()
    if timeout is None:
        return await coro
    else:
        async with asyncio.timeout(delay=timeout):
            return await coro


async def side_run(effect: AsyncSide[A]) -> A:
    """
        Simple asynchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    with closing(runner(effect, AsyncPure, AsyncContinuation)) as gen:
        try:
            entity = next(gen)
            while True:
                pure = None
                if isinstance(entity, AsyncPrime):
                    pure = await _prime_exec(entity.prime, entity.timeout, to_thread=False)
                elif isinstance(entity, AsyncPrimeThread):
                    pure = await _prime_exec(entity.prime_thread, entity.timeout, to_thread=True)
                else:
                    panic_on_violations(AsyncSide.__name__, 'async side runner method', entity)
                entity = gen.send(AsyncPure(pure))
        except StopIteration as finish:
            return cast(A, finish.value)


async def side_safe_run(effect: AsyncSide[A]) -> Result[A, Exception]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
    """
    try:
        res = await side_run(effect)
        return cast(Result[A, Exception], Ok(res))
    except (MonadError, asyncio.CancelledError):
        raise
    except Exception as err:
        return cast(Result[A, Exception], Err(err))


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


async def _prime_catch(effect, timeout, to_thread):
    try:
        return Ok(await _prime_exec(effect, timeout, to_thread))
    except (MonadError, asyncio.CancelledError):
        raise
    except Exception as error:
        return Err(error)


async def side_rebuild_run(effect: AsyncSide[A]) -> Report[Any, AsyncSide[A]]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
    """
    with closing(rebuild_runner(effect, AsyncPure, AsyncContinuation)) as gen:
        try:
            yld: Yield = next(gen)
            entity, last_success, stack = yld.entity, yld.last_success, yld.stack
            while True:
                pure = None
                if isinstance(entity, AsyncPrime):
                    r = await _prime_catch(entity.prime, entity.timeout, to_thread=False)
                    if isinstance(r, Err):
                        rest = _rebuild_from_prime(entity.prime, entity.timeout, stack, to_thread=False)
                        return cast(Report[Any, AsyncSide[A]], Report(last_success, r.error, entity.prime, rest))
                    pure = r.value

                elif isinstance(entity, AsyncPrimeThread):
                    r = await _prime_catch(entity.prime_thread, entity.timeout, to_thread=True)
                    if isinstance(r, Err):
                        rest = _rebuild_from_prime(entity.prime_thread, entity.timeout, stack, to_thread=True)
                        return cast(Report[Any, AsyncSide[A]], Report(last_success, r.error, entity.prime_thread, rest))
                    pure = r.value

                else:
                    panic_on_violations(AsyncSide.__name__, 'async side runner method', entity)

                yld: Yield = gen.send(AsyncPure(pure))
                entity, last_success, stack = yld.entity, yld.last_success, yld.stack
        except StopIteration as finish:
            rtn: Return = finish.value
            last_success, error, faulty, stack = rtn.last_success, rtn.error, rtn.faulty, rtn.stack
            rest = _rebuild_from_pure(last_success, stack)
            return cast(Report[Any, AsyncSide[A]], Report(last_success, error, faulty, remainder=rest))


async def insist(
        effect: AsyncSide[A],
        attempts: int = 1,
        pause: Union[int, float] = 0
) -> Report[Any, AsyncSide[A]]:
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
    """
    chain, report = effect, Report(None, None, None, effect)
    for _ in range(attempts):
        report = await side_rebuild_run(chain)
        if not report.completed_successfully:
            chain = report.remainder
            await asyncio.sleep(pause)
            continue
        break
    return cast(Report[Any, AsyncSide[A]], report)
