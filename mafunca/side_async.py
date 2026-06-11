from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, Any, Union, Optional


from mafunca.specials import panic_on_impure
from mafunca._lazy_support import panic_on_coroutine


__all__ = [
    "AsyncSide",
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
            :raises MonadError: coroutine or marked as impure functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        panic_on_impure(self.__class__.__name__, 'map', fn)
        return _AsyncContinuation(self, lambda a: _AsyncPure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'AsyncSide[B]']) -> 'AsyncSide[B]':
        """
            The function that returns the effect must be synchronous.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine or marked as impure functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        panic_on_impure(self.__class__.__name__, 'bind', fn)
        return _AsyncContinuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'AsyncSide[A]':
        return _AsyncPure(value)

    @staticmethod
    def effect(fn: Callable[[], Awaitable[A]], timeout: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        return _AsyncEffect(fn, timeout)

    @staticmethod
    def effect_to_thread(fn: Callable[[], A], timeout: Optional[Union[int, float]] = None) -> 'AsyncSide[A]':
        """
            Only for synchronous functions - will be executed in a separate thread
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, AsyncSide.__name__, 'effect_to_thread')
        return _AsyncEffectThread(fn, timeout)


#  IMPORTANT
#  All nodes except primary effects in all lazy monads must have the same attribute names
#  Code-level convention

@dataclass(frozen=True, slots=True, repr=True)
class _AsyncPure(AsyncSide[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class _AsyncEffect(AsyncSide[A]):
    prime: Callable[[], Awaitable[A]]
    timeout: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class _AsyncEffectThread(AsyncSide[A]):
    prime: Callable[[], A]
    timeout: Optional[Union[int, float]]


@dataclass(frozen=True, slots=True, repr=True)
class _AsyncContinuation(AsyncSide[B]):
    current: AsyncSide[Any]
    next: Callable[[Any], AsyncSide[B]]
    next_origin: Callable[[Any], Union[AsyncSide[B], B]]
