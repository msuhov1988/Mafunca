from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union, ParamSpec, cast, Any, Never

from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Ok, Err, Result
from mafunca.curry import curry2, curry3, curry4, curry
from mafunca.common.exceptions import MonadError
from mafunca.specials import panic_on_impure


__all__ = [
    'TMaybeR',
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
class TMaybeR(Generic[T, E]):
    """Container for a composite value of the form 'Maybe[Result[T, E]]'"""
    inner: Maybe[Result[T, E]]

    @staticmethod
    def ok(value: T) -> 'TMaybeR[T, Never]':
        return TMaybeR(Just(Ok(value)))

    @staticmethod
    def error(error: E) -> 'TMaybeR[Never, E]':
        return TMaybeR(Just(Err(error)))

    @staticmethod
    def nothing() -> 'TMaybeR[T, Never]':
        return TMaybeR(Nothing())

    @staticmethod
    def wrap_result(result: Result[T, E]) -> 'TMaybeR[T, E]':
        return TMaybeR(Just(result))

    @staticmethod
    def wrap_maybe(maybe: Maybe[T]) -> 'TMaybeR[T, Never]':
        if isinstance(maybe, Nothing):
            return TMaybeR(maybe)
        return TMaybeR(Just(Ok(maybe.value)))

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

    def map(self, fn: Callable[[T], R]) -> 'TMaybeR[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map', fn)
        if isinstance(self.inner, Nothing):
            return cast(TMaybeR[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(TMaybeR[R, E], self)
        value = fn(result.value)
        return TMaybeR(Just(Ok(value)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'TMaybeR[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_maybe', fn)
        if isinstance(self.inner, Nothing):
            return cast(TMaybeR[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(TMaybeR[R, E], self)
        return TMaybeR.wrap_maybe(fn(result.value))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'TMaybeR[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_result', fn)
        if isinstance(self.inner, Nothing):
            return cast(TMaybeR[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(TMaybeR[R, E], self)
        return TMaybeR.wrap_result(fn(result.value))

    def bind(self, fn: Callable[[T], 'TMaybeR[R, E]']) -> 'TMaybeR[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'bind', fn)
        if isinstance(self.inner, Nothing):
            return cast(TMaybeR[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(TMaybeR[R, E], self)
        return fn(result.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'TMaybeR[T, NewE]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_error', fn)
        if isinstance(self.inner, Nothing):
            return cast(TMaybeR[T, NewE], self)
        result = self.inner.value
        if isinstance(result, Ok):
            return cast(TMaybeR[T, NewE], self)
        return TMaybeR.error(fn(result.error))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Nothing) or isinstance(inner.value, Err):
            return alter
        return inner.value.value

    def unfold(self, *, just: Callable[[Result[T, E]], R], nothing: Callable[[], R]) -> R:
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'unfold', just, nothing)
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
) -> TMaybeR[R, E]:
    """Wraps the result based on 'is_nullable' predicate."""
    return TMaybeR.nothing() if is_nullable(value) else TMaybeR.ok(value)


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
        :raises MonadError: if the passed function is marked as impure
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, TMaybeR[R, Exception]]:
        panic_on_impure('maybe_transformer', 'from_try', fn)

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> TMaybeR[R, Exception]:
            try:
                return from_null(fn(*args, **kwargs), is_nullable)
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return TMaybeR.error(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: TMaybeR[Callable[[T], R], E], val: TMaybeR[T, E]) -> TMaybeR[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
        :raises MonadError: if the passed function is marked as impure
    """
    if isinstance(fn.inner, Nothing):
        return cast(TMaybeR[R, E], fn)
    if isinstance(fn.inner.value, Err):
        return cast(TMaybeR[R, E], fn)
    panic_on_impure('maybe_transformer', 'ap', fn.inner.value.value)
    if isinstance(val.inner, Nothing):
        return cast(TMaybeR[R, E], val)
    if isinstance(val.inner.value, Err):
        return cast(TMaybeR[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return TMaybeR.ok(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: TMaybeR[A1, E],
        arg2: TMaybeR[A2, E]
) -> TMaybeR[R, E]:
    """
        For a function with two POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(TMaybeR.ok(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: TMaybeR[A1, E],
        arg2: TMaybeR[A2, E],
        arg3: TMaybeR[A3, E]
) -> TMaybeR[R, E]:
    """
        For a function with three POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(TMaybeR.ok(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: TMaybeR[A1, E],
        arg2: TMaybeR[A2, E],
        arg3: TMaybeR[A3, E],
        arg4: TMaybeR[A4, E]
) -> TMaybeR[R, E]:
    """
        For a function with four POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(ap(TMaybeR.ok(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: TMaybeR[Any, E]) -> TMaybeR[Union[Callable, R], E]:
    """
       For a function with an arbitrary number of POSITIONAL arguments.
       Wraps the passed function in the container and applies the applicative method.

       ATTENTION. When an incomplete number of arguments is passed,
       a curried version with partially applied arguments will be returned.
       However, since each call curries the passed function,
       the partially applied arguments from the previous step are not preserved.
       :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    result = TMaybeR.ok(curry(fn))
    for arg in args:
        result = ap(result, arg)
    return result
