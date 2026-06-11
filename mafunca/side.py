from dataclasses import dataclass
from collections.abc import Callable
from typing import Generic, TypeVar, Any, Union

from mafunca.specials import panic_on_impure
from mafunca._lazy_support import panic_on_coroutine  # noqa
from mafunca.result import Result, Ok, Err


__all__ = [
    "Side",
]


A = TypeVar("A")
B = TypeVar("B")
E = TypeVar("E")


class Side(Generic[A]):
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """
    def map(self, fn: Callable[[A], B]) -> 'Side[B]':
        """:raises MonadError: coroutine or marked as impure functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        panic_on_impure(self.__class__.__name__, 'map', fn)
        return _Continuation(self, lambda a: _Pure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'Side[B]']) -> 'Side[B]':
        """:raises MonadError: coroutine or marked as impure functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        panic_on_impure(self.__class__.__name__, 'bind', fn)
        return _Continuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'Side[A]':
        return _Pure(value)

    @staticmethod
    def effect(fn: Callable[[], A]) -> 'Side[A]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, Side.__name__, 'effect')
        return _Effect(fn)


#  IMPORTANT
#  All nodes except primary effects in all lazy monads must have the same attribute names
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
    next_origin: Callable[[Any], Union[Side[B], B]]


# all methods in transformers are implemented without relying on the methods of underlying monads
# so as not to duplicate panics on impure functions

class TSideR(Generic[A, E]):
    """
        A transformer for SYNCHRONOUS ONLY effects.

        It is built over a value of the form Result[A,E] or an effect of the form Callable[[], Result[A, E]].

        Lazy: not executed until the corresponding executor is called.
    """
    def map(self, fn: Callable[[A], B]) -> 'TSideR[B, E]':
        """:raises MonadError: coroutine or marked as impure functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        panic_on_impure(self.__class__.__name__, 'map', fn)

        def continuation(arg: Result[A, E]) -> 'TSideR[B, E]':
            if isinstance(arg, Err):
                return _TPureR(arg)
            return _TPureR(Ok(fn(arg.value)))

        return _TContinuationR(self, continuation, fn)

    def map_result(self, fn: Callable[[A], Result[B, E]]) -> 'TSideR[B, E]':
        """:raises MonadError: coroutine or marked as impure functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map_result')
        panic_on_impure(self.__class__.__name__, 'map_result', fn)

        def continuation(arg: Result[A, E]) -> 'TSideR[B, E]':
            if isinstance(arg, Err):
                return _TPureR(arg)
            return _TPureR(fn(arg.value))

        return _TContinuationR(self, continuation, fn)

    def bind(self, fn: Callable[[A], 'TSideR[B, E]']) -> 'TSideR[B, E]':
        """:raises MonadError: coroutine or marked as impure functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        panic_on_impure(self.__class__.__name__, 'bind', fn)
        return _TContinuationR(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'TSideR[A, E]':
        return _TPureR(Ok(value))

    @staticmethod
    def pure_error(error: E) -> 'TSideR[A, E]':
        return _TPureR(Err(error))

    @staticmethod
    def wrap_result(value: Result[A, E]) -> 'TSideR[A, E]':
        return _TPureR(value)

    @staticmethod
    def effect(fn: Callable[[], Result[A, E]]) -> 'TSideR[A, E]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, TSideR.__name__, 'effect')
        return _TEffectR(fn)


#  IMPORTANT
#  All nodes except primary effects in all lazy monads must have the same attribute names
#  Code-level convention

@dataclass(frozen=True, slots=True, repr=True)
class _TPureR(TSideR[A, E]):
    value: Result[A, E]


@dataclass(frozen=True, slots=True, repr=True)
class _TEffectR(TSideR[A, E]):
    prime: Callable[[], Result[A, E]]


@dataclass(frozen=True, slots=True, repr=True)
class _TContinuationR(TSideR[B, E]):
    current: TSideR[Any, E]
    next: Callable[[Any], TSideR[B, E]]
    next_origin: Callable[[Any], Union[TSideR[B, E], Result[B, E], B]]
