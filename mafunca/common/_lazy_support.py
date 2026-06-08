import asyncio
import inspect
from collections.abc import Callable, Awaitable
from typing import TypeVar, Tuple, Union, Optional

from mafunca.common.exceptions import MonadError


A = TypeVar("A")
B = TypeVar("B")


def prime_catch(prime: Callable[[], A]) -> Union[Tuple[A, None], Tuple[None, Exception]]:
    """MonadError is not suppressed"""
    try:
        entity = prime()
        return entity, None
    except MonadError:
        raise
    except Exception as err:
        return None, err


async def async_prime_catch(
        prime: Callable[[], Awaitable[A]],
        delay: Optional[Union[int, float]]
) -> Union[Tuple[A, None], Tuple[None, Exception]]:
    """
        asyncio.CancelledError is not suppressed.

        MonadError is not suppressed
        :raises TimeoutError: delay is set and the waiting time has been exceeded.
    """
    try:
        if delay is None:
            entity = await prime()
        else:
            async with asyncio.timeout(delay=delay):
                entity = await prime()
        return entity, None
    except asyncio.CancelledError:
        raise
    except MonadError:
        raise
    except Exception as err:
        return None, err


async def async_prime_thread_catch(
        prime_sync: Callable[[], A],
        delay: Optional[Union[int, float]]
) -> Union[Tuple[A, None], Tuple[None, Exception]]:
    """
        Performs a synchronous function in a separate thread

        asyncio.CancelledError is not suppressed.

        MonadError is not suppressed
        :raises TimeoutError: delay is set and the waiting time has been exceeded.
    """
    try:
        if delay is None:
            entity = await asyncio.to_thread(prime_sync)
        else:
            async with asyncio.timeout(delay=delay):
                entity = await asyncio.to_thread(prime_sync)
        return entity, None
    except asyncio.CancelledError:
        raise
    except MonadError:
        raise
    except Exception as err:
        return None, err


def continuation_catch(cont: Callable[[A], B], arg: A) -> Union[Tuple[B, None], Tuple[None, Exception]]:
    """MonadError is not suppressed"""
    try:
        entity = cont(arg)
        return entity, None
    except MonadError:
        raise
    except Exception as err:
        return None, err


def panic_on_violations(monad_name: str, runner_name: str, entity):
    """
        :raises MonadError: unknown node.
    """
    raise MonadError(
        monad=monad_name,
        method=runner_name,
        message=f"violation of the contract - unknown node {entity}.\n"
    )


def panic_on_coroutine(fn: Callable, monad_name: str, method_name: str):
    """
       Panic when the monadic contract is violated - function must be sync.
       :raises MonadError: async function can not be used
    """
    if inspect.iscoroutinefunction(fn):
        raise MonadError(
            monad=monad_name,
            method=method_name,
            message=f"function '{fn}' - async function can not be used"
        )
