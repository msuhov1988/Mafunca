from typing import TypeVar, Union, Optional, List, Tuple
import inspect
from collections.abc import Callable, Awaitable

from mafunca.common.resilient_support import Uncaught


_ORIGIN_LINK = "__mafunca_resilient_origin__"


def continuer_sync(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable:
    """
        Special sync closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    def continuer_sync_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return fn(arg)

    setattr(continuer_sync_inner, _ORIGIN_LINK, fn)
    return continuer_sync_inner


def catcher_sync(fn: Callable) -> Callable:
    """Special sync closure for catching errors"""
    def catcher_sync_inner(arg):
        if isinstance(arg, Uncaught):
            return fn(arg.error)
        return arg

    setattr(catcher_sync_inner, _ORIGIN_LINK, fn)
    return catcher_sync_inner


def ensurer_sync(fn: Callable) -> Callable:
    """A sync closure simulating finally"""
    def ensurer_sync_inner(arg):
        fn()
        return arg

    setattr(ensurer_sync_inner, _ORIGIN_LINK, fn)
    return ensurer_sync_inner


T = TypeVar('T')


async def maybe_await(obj: Union[Awaitable[T], T]) -> T:
    return await obj if inspect.isawaitable(obj) else obj


def continuer(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable[..., Awaitable]:
    """
        Special async closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    async def continuer_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return await maybe_await(fn(arg))

    setattr(continuer_inner, _ORIGIN_LINK, fn)
    return continuer_inner


def catcher(fn: Callable) -> Callable[..., Awaitable]:
    """Special async closure for catching errors"""
    async def catcher_inner(arg):
        if isinstance(arg, Uncaught):
            return await maybe_await(fn(arg.error))
        return arg

    setattr(catcher_inner, _ORIGIN_LINK, fn)
    return catcher_inner


def ensurer(fn: Callable) -> Callable[..., Awaitable]:
    """An async closure simulating finally"""
    async def ensurer_inner(arg):
        await maybe_await(fn())
        return arg

    setattr(ensurer_inner, _ORIGIN_LINK, fn)
    return ensurer_inner


def get_origin(closure: Callable) -> Callable:
    """Extract origin function from closures like 'continuer' and etc"""
    origin = getattr(closure, _ORIGIN_LINK, None)
    if origin is None:
        return closure
    return origin


def get_indexes_for_execution(steps: Optional[int], inverted_cons: List) -> Tuple[int, int]:
    """Processing of the steps parameter in resilient monads"""
    chain_length = len(inverted_cons) + 1  # +1 since prime always comes first, in addition to inverted_cons
    bounded_steps = chain_length if steps is None or steps > chain_length else steps
    bounded_steps_without_prime = bounded_steps - 1
    first_cont_index = len(inverted_cons) - 1  # inverted_cons is an inverted list, the last is the first
    last_cont_index = first_cont_index - bounded_steps_without_prime
    return first_cont_index, last_cont_index
