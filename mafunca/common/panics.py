import inspect
from collections.abc import Callable

from mafunca.common.exceptions import MonadError, CurryBadFunctionError


def extract_name(func) -> str:
    return getattr(func, "__qualname__", getattr(func, "__name__", f"{func}"))


def on_coroutine(fn: Callable, monad_name: str, method: str):
    """
       Panic when the monadic contract is violated - function must be sync.
       :raises MonadError:
    """
    if inspect.iscoroutinefunction(fn):
        raise MonadError(
            monad_name,
            method,
            message=f"function '{extract_name(fn)}' - async function can not be used"
        )


def on_sync(fn: Callable, monad_name: str, method: str):
    """
       Panic when the monadic contract is violated - function must be async.
       :raises MonadError:
    """
    if not inspect.iscoroutinefunction(fn):
        raise MonadError(
            monad_name,
            method,
            message=f"function '{extract_name(fn)}' - sync function can not be used")


def on_monadic_result(result, fn: Callable, monad, method: str):
    """
       Panic when the monadic contract is violated - the function should not return a monad.
       :raises MonadError:
    """
    if isinstance(result, monad):
        name = monad.__name__
        raise MonadError(
            name,
            method,
            f"return value {result} of applying function '{extract_name(fn)}' - must not be '{name}' entity"
        )


def on_another_instance(result, fn: Callable, monad, method: str):
    """
       Panic when the monadic contract is violated - the function should return the same instance.
       :raises MonadError:
    """
    if not isinstance(result, monad):
        name = monad.__name__
        raise MonadError(
            name,
            method,
            f"return value {result} of applying function '{extract_name(fn)}' must be '{name}' entity"
        )


def on_bad_curried(func):
    """
       Panic on improper entity for currying.
       :raises CurryBadFunctionError:
    """
    if not inspect.isfunction(func):
        raise CurryBadFunctionError(func_name=extract_name(func), err="must be a callable")
    if inspect.isbuiltin(func):
        raise CurryBadFunctionError(func_name=extract_name(func), err="should not be a built-in function")
    if inspect.ismethod(func):
        raise CurryBadFunctionError(func_name=extract_name(func), err="should not be a bound method")


def curry_on_coroutine(func: Callable):
    """
       Panic on async function in sync curry decorator.
       :raises CurryBadFunctionError:
    """
    if inspect.iscoroutinefunction(func):
        raise CurryBadFunctionError(
            func_name=extract_name(func),
            err="should not be an async function. Use async curry decorator instead."
        )


def curry_on_sync(func: Callable):
    """
       Panic on sync function in async curry decorator.
       :raises CurryBadFunctionError:
    """
    if not inspect.iscoroutinefunction(func):
        raise CurryBadFunctionError(
            func_name=extract_name(func),
            err="should not be a sync function. Use sync curry decorator instead."
        )
