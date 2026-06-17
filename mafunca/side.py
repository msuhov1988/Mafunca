from dataclasses import dataclass
from collections.abc import Callable
from typing import Generic, TypeVar, Any, Union, Never

from mafunca._lazy_support import panic_on_coroutine
from mafunca.result import Result, Ok, Err


__all__ = [
    "Side",
    "SideT",
]


A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")
E = TypeVar("E")


class Side(Generic[A]):
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """

    @staticmethod
    def pure(value: A) -> 'Side[A]':
        return _Pure(value)

    @staticmethod
    def effect(fn: Callable[[], A]) -> 'Side[A]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, Side.__name__, 'effect')
        return _Effect(fn)

    def map(self, fn: Callable[[A], B]) -> 'Side[B]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return _Continuation(self, lambda a: _Pure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'Side[B]']) -> 'Side[B]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return _Continuation(self, fn, fn)


#  IMPORTANT
#  All nodes such as Pure and Continuation in all deferred pipelines must have the same attribute names
#  Code-level convention

@dataclass(frozen=True, slots=True, repr=True)
class _Pure(Side[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class _Effect(Side[A]):
    prime: Callable[[], A]


@dataclass(frozen=True, slots=True, repr=True)
class _Continuation(Side[B]):
    current: Side[Any]
    next: Callable[[Any], Side[B]]
    next_origin: Callable[[Any], Union[Side[B], C]]


@dataclass(frozen=True, slots=True, repr=True)
class SideT(Generic[A, E]):
    """
        A transformer for SYNCHRONOUS ONLY effects.

        Container for a composite value of the form 'Side[Result[A, E]]'.

        Lazy: not executed until the corresponding executor is called.
    """
    inner: Side[Result[A, E]]

    @staticmethod
    def pure(value: A) -> 'SideT[A, Never]':
        return SideT(_Pure(Ok(value)))

    @staticmethod
    def error(error: E) -> 'SideT[Never, E]':
        return SideT(_Pure(Err(error)))

    @staticmethod
    def wrap_result(result: Result[A, E]) -> 'SideT[A, E]':
        return SideT(_Pure(result))

    @staticmethod
    def wrap_side(side: Side[A]) -> 'SideT[A, Never]':

        def continuation(arg: A) -> Side[Result[A, Never]]:
            return _Pure(Ok(arg))

        return SideT(_Continuation(side, continuation, continuation))

    @staticmethod
    def effect(fn: Callable[[], Result[A, E]]) -> 'SideT[A, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, SideT.__name__, 'effect')
        return SideT(_Effect(fn))

    def map(self, fn: Callable[[A], B]) -> 'SideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return SideT(_Continuation(self.inner, lambda res: _Pure(res.map(fn)), fn))

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> 'SideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        return SideT(_Continuation(self.inner, lambda res: _Pure(res.bind(fn)), fn))

    def bind(self, fn: Callable[[A], 'SideT[B, E]']) -> 'SideT[B, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')

        def continuation(arg: Result[A, E]) -> Side[Result[B, E]]:
            if isinstance(arg, Err):
                return _Pure(arg)
            return fn(arg.value).inner

        return SideT(_Continuation(self.inner, continuation, fn))
