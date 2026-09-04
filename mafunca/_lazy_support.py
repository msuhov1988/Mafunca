import inspect
from typing import Any

from mafunca.common.exceptions import MonadError


def _extract_name(func: Any) -> str:
    return getattr(func, "__qualname__", getattr(func, "__name__", f"{func}"))


def panic_on_coroutine(fn: Any, monad_name: str, method_name: str):
    """
       Internal.
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
