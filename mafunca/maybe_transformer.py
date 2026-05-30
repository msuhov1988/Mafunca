from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union, ParamSpec, cast, Any

from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Ok, Err, Result
from mafunca.curry import curry2, curry3, curry4, curry, Curry
from mafunca.common.exceptions import MonadError
from mafunca.specials import _panic_on_impure  # noqa


__all__ = [
    'MaybeResultT',
    'from_null',
    'from_try',
    'ap',
    'lift2',
    'lift3',
    'lift4',
    'lift',
]


T = TypeVar("T")
E = TypeVar("E")
NewE = TypeVar('NewE')
R = TypeVar("R")


# all methods are implemented without relying on the methods of underlying monads
# so as not to duplicate panics on impure functions


@dataclass(frozen=True, slots=True, repr=True)
class MaybeResultT(Generic[T, E]):
    """Container for a composite value of the form 'Maybe[Result[T, E]]'"""
    inner: Maybe[Result[T, E]]

    @staticmethod
    def ok(value: T) -> 'MaybeResultT[T, E]':
        return MaybeResultT(Just(Ok(value)))

    @staticmethod
    def error(error: E) -> 'MaybeResultT[T, E]':
        return MaybeResultT(Just(Err(error)))

    @staticmethod
    def nothing() -> 'MaybeResultT[T, E]':
        return MaybeResultT(Nothing())

    @staticmethod
    def wrap_result(result: Result[T, E]) -> 'MaybeResultT[T, E]':
        return MaybeResultT(Just(result))

    @staticmethod
    def wrap_maybe(maybe: Maybe[T]) -> 'MaybeResultT[T, E]':
        if isinstance(maybe, Nothing):
            return MaybeResultT(maybe)
        return MaybeResultT(Just(Ok(maybe.value)))

    @property
    def is_ok(self) -> bool:
        inner = self.inner
        return isinstance(inner, Just) and inner.value.is_ok

    @property
    def is_error(self) -> bool:
        inner = self.inner
        return isinstance(inner, Just) and inner.value.is_error

    @property
    def is_nothing(self) -> bool:
        return self.inner.is_nothing

    def map(self, fn: Callable[[T], R]) -> 'MaybeResultT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        if isinstance(self.inner, Nothing):
            return cast(MaybeResultT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeResultT[R, E], self)
        value = fn(result.value)
        return MaybeResultT(Just(Ok(value)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'MaybeResultT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_maybe', fn)
        if isinstance(self.inner, Nothing):
            return cast(MaybeResultT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeResultT[R, E], self)
        return MaybeResultT.wrap_maybe(fn(result.value))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'MaybeResultT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_result', fn)
        if isinstance(self.inner, Nothing):
            return cast(MaybeResultT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeResultT[R, E], self)
        return MaybeResultT.wrap_result(fn(result.value))

    def bind(self, fn: Callable[[T], 'MaybeResultT[R, E]']) -> 'MaybeResultT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        if isinstance(self.inner, Nothing):
            return cast(MaybeResultT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeResultT[R, E], self)
        return fn(result.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'MaybeResultT[T, NewE]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_error', fn)
        if isinstance(self.inner, Nothing):
            return cast(MaybeResultT[T, NewE], self)
        result = self.inner.value
        if isinstance(result, Ok):
            return cast(MaybeResultT[T, NewE], self)
        return MaybeResultT.error(fn(result.error))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Nothing) or isinstance(inner.value, Err):
            return alter
        return inner.value.value

    def unfold(self, *, just: Callable[[Result[T, E]], R], nothing: Callable[[], R]) -> R:
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', just, nothing)
        if isinstance(self.inner, Nothing):
            return nothing()
        return just(self.inner.value)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_null(
        value: R,
        is_nullable: Callable[[R], bool] = lambda v: v is None
) -> MaybeResultT[R, E]:
    """Wraps the result based on 'is_nullable' predicate."""
    return MaybeResultT.nothing() if is_nullable(value) else MaybeResultT.ok(value)


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
        :raises MonadError: if the passed function is marked as impure
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, MaybeResultT[R, Exception]]:
        _panic_on_impure('maybe_transformer', 'from_try', fn)

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> MaybeResultT[R, Exception]:
            try:
                return from_null(fn(*args, **kwargs), is_nullable)
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return MaybeResultT.error(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: MaybeResultT[Callable[[T], R], E], val: MaybeResultT[T, E]) -> MaybeResultT[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
        :raises MonadError: if the passed function is marked as impure
    """
    if isinstance(fn.inner, Nothing):
        return cast(MaybeResultT[R, E], fn)
    if isinstance(fn.inner.value, Err):
        return cast(MaybeResultT[R, E], fn)
    _panic_on_impure('maybe_transformer', 'ap', fn.inner.value.value)
    if isinstance(val.inner, Nothing):
        return cast(MaybeResultT[R, E], val)
    if isinstance(val.inner.value, Err):
        return cast(MaybeResultT[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return MaybeResultT.ok(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: MaybeResultT[A1, E],
        arg2: MaybeResultT[A2, E]
) -> MaybeResultT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(MaybeResultT.ok(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: MaybeResultT[A1, E],
        arg2: MaybeResultT[A2, E],
        arg3: MaybeResultT[A3, E]
) -> MaybeResultT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(MaybeResultT.ok(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: MaybeResultT[A1, E],
        arg2: MaybeResultT[A2, E],
        arg3: MaybeResultT[A3, E],
        arg4: MaybeResultT[A4, E]
) -> MaybeResultT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(ap(MaybeResultT.ok(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: MaybeResultT[Any, E]) -> MaybeResultT[Union[Curry[R], R], E]:
    """
       Wraps the passed function in the container and applies the applicative method.
       If fewer arguments are passed than the function requires, it returns a curried version in the container
       that waits for the remaining arguments
       :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    result = MaybeResultT.ok(curry(fn) if not isinstance(fn, Curry) else fn)
    for arg in args:
        result = ap(result, arg)
    return result
