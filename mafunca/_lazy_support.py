import asyncio
import inspect
from collections.abc import Callable, Awaitable
from typing import TypeVar, Union, Optional

from mafunca.common.exceptions import MonadError
from mafunca.result import Ok, Err, Result


A = TypeVar("A")
B = TypeVar("B")


def prime_catch(prime: Callable[[], A]) -> Result[A, Exception]:
    """MonadError is not suppressed"""
    try:
        return Ok(prime())
    except MonadError:
        raise
    except Exception as err:
        return Err(err)


async def async_prime_catch(
        prime: Callable[[], Awaitable[A]],
        delay: Optional[Union[int, float]]
) -> Result[A, Exception]:
    """
        asyncio.CancelledError is not suppressed.

        MonadError is not suppressed
    """
    try:
        if delay is None:
            entity = await prime()
        else:
            async with asyncio.timeout(delay=delay):
                entity = await prime()
        return Ok(entity)
    except asyncio.CancelledError:
        raise
    except MonadError:
        raise
    except Exception as err:
        return Err(err)


async def async_prime_thread_catch(
        prime_sync: Callable[[], A],
        delay: Optional[Union[int, float]]
) -> Result[A, Exception]:
    """
        Performs a synchronous function in a separate thread

        asyncio.CancelledError is not suppressed.

        MonadError is not suppressed
    """
    try:
        if delay is None:
            entity = await asyncio.to_thread(prime_sync)
        else:
            async with asyncio.timeout(delay=delay):
                entity = await asyncio.to_thread(prime_sync)
        return Ok(entity)
    except asyncio.CancelledError:
        raise
    except MonadError:
        raise
    except Exception as err:
        return Err(err)


def continuation_catch(cont: Callable[[A], B], arg: A) -> Result[B, Exception]:
    """MonadError is not suppressed"""
    try:
        return Ok(cont(arg))
    except MonadError:
        raise
    except Exception as err:
        return Err(err)


def panic_on_violations(monad_name: str, runner_name: str, entity):
    """
        :raises MonadError: unknown node.
    """
    raise MonadError(
        monad=monad_name,
        method=runner_name,
        message=f"violation of the contract - unknown node {entity}.\n"
    )


def _extract_name(func) -> str:
    return getattr(func, "__qualname__", getattr(func, "__name__", f"{func}"))


def panic_on_coroutine(fn: Callable, monad_name: str, method_name: str):
    """
       Panic when the monadic contract is violated - function must be sync.
       :raises MonadError: async function can not be used
    """
    is_coro = inspect.iscoroutinefunction(fn)
    if not is_coro:
        is_coro = inspect.iscoroutinefunction(getattr(fn, "__call__", None))
    if is_coro:
        raise MonadError(
            monad=monad_name,
            method=method_name,
            message=f"function '{_extract_name(fn)}' - async function can not be used"
        )
