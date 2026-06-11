from contextlib import closing
import asyncio
from collections.abc import Callable
from typing import TypeVar, Union, Any, cast, List, Tuple

from mafunca.common.exceptions import MonadError
from mafunca._lazy_support import panic_on_violations
from mafunca._lazy_support import runner, rebuild_runner, Yield, Return, rebuild_from
from mafunca.result import Result, Ok, Err
from mafunca.side_async import AsyncSide
from mafunca.side_async import _AsyncPure, _AsyncEffect, _AsyncEffectThread, _AsyncContinuation  # noqa
from mafunca.side_rebuild_report import Report


__all__ = [
    "run_async",
    "run_safe_async",
    "run_rebuild_async",
    "insist_async"
]


A = TypeVar("A")


async def _execute_async_effect(entity: Union[_AsyncEffect[A], _AsyncEffectThread[A]], method: str) -> A:
    """
        Execute async or sync in thread effect with timeout if set
        :raises MonadError: unknown type of entity
    """
    coro = None
    if isinstance(entity, _AsyncEffect):
        coro = entity.prime()
    elif isinstance(entity, _AsyncEffectThread):
        coro = asyncio.to_thread(entity.prime)
    if coro is None:
        panic_on_violations(AsyncSide.__name__, method, entity)
    if entity.timeout is None:
        return await coro
    else:
        async with asyncio.timeout(delay=entity.timeout):
            return await coro


async def run_async(effect: AsyncSide[A]) -> A:
    """
        Simple asynchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    with closing(runner(effect, _AsyncPure, _AsyncContinuation)) as gen:
        try:
            entity = next(gen)
            while True:
                out = await _execute_async_effect(entity, method="run_async")
                entity = gen.send(AsyncSide.pure(out))
        except StopIteration as finish:
            return cast(A, finish.value)


async def run_safe_async(effect: AsyncSide[A]) -> Result[A, Exception]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.
    """
    try:
        res = await run_async(effect)
        return cast(Result[A, Exception], Ok(res))
    except (MonadError, asyncio.CancelledError):
        raise
    except Exception as err:
        return cast(Result[A, Exception], Err(err))


async def run_rebuild_async(effect: AsyncSide[A]) -> Report[Any, AsyncSide[A]]:
    """
        Asynchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

        MonadError is not suppressed.

        asyncio.CancelledError is not suppressed.

        :raises MonadError: violations of the contract
    """
    with closing(rebuild_runner(effect, _AsyncPure, _AsyncContinuation)) as gen:
        try:
            yld: Yield = next(gen)
            entity, last_success, stack = yld.entity, yld.last_success, yld.stack
            while True:
                try:
                    out = Ok(await _execute_async_effect(entity, method='run_rebuild_async'))
                except (MonadError, asyncio.CancelledError):
                    raise
                except Exception as error:
                    rest = rebuild_from(entity, stack, _AsyncContinuation)
                    return cast(Report[Any, AsyncSide[A]], Report(last_success, error, entity.prime, rest))
                yld: Yield = gen.send(AsyncSide.pure(out.value))
                entity, last_success, stack = yld.entity, yld.last_success, yld.stack
        except StopIteration as finish:
            rtn: Return = finish.value
            last_success, error, faulty, stack = rtn.last_success, rtn.error, rtn.faulty, rtn.stack
            rest = rebuild_from(AsyncSide.pure(last_success), stack, _AsyncContinuation)
            return cast(Report[Any, AsyncSide[A]], Report(last_success, error, faulty, remainder=rest))


async def insist_async(
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
        report = await run_rebuild_async(chain)
        if not report.completed_successfully:
            chain = report.remainder
            await asyncio.sleep(pause)
            continue
        break
    return cast(Report[Any, AsyncSide[A]], report)
