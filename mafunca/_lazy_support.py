import inspect
from dataclasses import dataclass
from collections.abc import Callable, Generator
from typing import TypeVar, TypeAlias, Type, Optional, Any, Tuple, List

from mafunca.common.exceptions import MonadError


def panic_on_violations(monad_name: str, runner_name: str, entity):
    """
        Internal.
        Panic when a contract is violated - improper use of binding methods
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


_Pure = TypeVar("_Pure")
_Cont = TypeVar("_Cont")


def runner(chain, pure_cls: Type[_Pure], continuation_cls: Type[_Cont]) -> Generator[Any, _Pure, Any]:
    """
        Internal.
        A general part that operates on pure nodes and sends side operations outside
    """
    entity, continuations = chain, list()
    while True:
        if isinstance(entity, continuation_cls):
            continuations.append(entity.next)
            entity = entity.current

        elif isinstance(entity, pure_cls):
            if len(continuations) == 0:
                return entity.value
            cont = continuations.pop()
            entity = cont(entity.value)

        else:
            entity = yield entity


_Stack: TypeAlias = List[Tuple[Callable[[Any], Any], Callable[[Any], Any]]]


@dataclass(frozen=True, slots=True)
class Yield:
    entity: Any
    last_success: Any
    stack: _Stack


@dataclass(frozen=True, slots=True)
class Return:
    last_success: Any
    error: Optional[Exception]
    faulty: Optional[Callable[[Any], Any]]
    stack: _Stack


def rebuild_runner(chain, pure_cls: Type[_Pure], continuation_cls: Type[_Cont]) -> Generator[Yield, _Pure, Return]:
    """
        Internal.
        A general part that operates on pure nodes and sends side operations outside.

        Catch errors.

        MonadError is not suppressed.
    """
    entity, continuations, last_success = chain, list(), None
    while True:
        if isinstance(entity, continuation_cls):
            continuations.append((entity.next, entity.next_origin))
            entity = entity.current

        elif isinstance(entity, pure_cls):
            last_success = entity.value
            if len(continuations) == 0:
                return Return(last_success, None, None, continuations)
            cont, cont_origin = continuations.pop()
            try:
                entity = cont(last_success)
            except MonadError:
                raise
            except Exception as err:
                continuations.append((cont, cont_origin))
                return Return(last_success, err, cont_origin, continuations)

        else:
            entity = yield Yield(entity, last_success, continuations)
