from dataclasses import dataclass
from collections.abc import Callable, Awaitable
from typing import Generic, TypeVar, Any, Union, Optional, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err


__all__ = [
    "AsyncSide",
    "AsyncSideT",
]


A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
E = TypeVar("E")


class AsyncSide(Generic[A]):
    """
        A monad for asynchronous effects.
        Lazy: not executed until the corresponding executor is called.
    """

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

    def map(self, fn: Callable[[A], B]) -> 'AsyncSide[B]':
        """
            Only for synchronous functions - pure calculation
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return _AsyncContinuation(self, lambda a: _AsyncPure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'AsyncSide[B]']) -> 'AsyncSide[B]':
        """
            The function that returns the effect must be synchronous.
            Asynchrony is assumed inside the effect
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return _AsyncContinuation(self, fn, fn)


#  IMPORTANT
#  All nodes such as Pure and Continuation in all deferred pipelines must have the same attribute names
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
    next_origin: Callable[[Any], Union[AsyncSide[B], C]]


@dataclass(frozen=True, slots=True, repr=True)
class AsyncSideT(Generic[A, E]):
    """
        A transformer for asynchronous effects.

        Container for a composite value of the form 'AsyncSide[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: AsyncSide[Result[A, E]]

    @staticmethod
    def pure(value: A) -> 'AsyncSideT[A, Never]':
        return AsyncSideT(_AsyncPure(Ok(value)))

    @staticmethod
    def error(error: E) -> 'AsyncSideT[Never, E]':
        return AsyncSideT(_AsyncPure(Err(error)))

    @staticmethod
    def wrap_result(result: Result[A, E]) -> 'AsyncSideT[A, E]':
        return AsyncSideT(_AsyncPure(result))

    @staticmethod
    def wrap_async_side(side: AsyncSide[A]) -> 'AsyncSideT[A, Never]':

        def continuation(arg: A) -> AsyncSide[Result[A, Never]]:
            return _AsyncPure(Ok(arg))

        return AsyncSideT(_AsyncContinuation(side, continuation, continuation))

    @staticmethod
    def effect(
            fn: Callable[[], Awaitable[Result[A, E]]],
            timeout: Optional[Union[int, float]] = None
    ) -> 'AsyncSideT[A, E]':
        return AsyncSideT(_AsyncEffect(fn, timeout))

    @staticmethod
    def effect_to_thread(
            fn: Callable[[], Result[A, E]],
            timeout: Optional[Union[int, float]] = None
    ) -> 'AsyncSideT[A, E]':
        """
            Only for synchronous functions - will be executed in a separate thread
            :raises MonadError: coroutine functions are not allowed
        """
        panic_on_coroutine(fn, AsyncSideT.__name__, 'effect_to_thread')
        return AsyncSideT(_AsyncEffectThread(fn, timeout))

    def map(self, fn: Callable[[A], B]) -> 'AsyncSideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return AsyncSideT(_AsyncContinuation(self.inner, lambda res: _AsyncPure(res.map(fn)), fn))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> 'AsyncSideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return AsyncSideT(_AsyncContinuation(self.inner, lambda res: _AsyncPure(res.bind(fn)), fn))

    def bind(self, fn: Callable[[A], 'AsyncSideT[B, E]']) -> 'AsyncSideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> AsyncSide[Result[B, E]]:
            if isinstance(arg, Err):
                return _AsyncPure(arg)
            return fn(arg.value).inner

        return AsyncSideT(_AsyncContinuation(self.inner, continuation, fn))
