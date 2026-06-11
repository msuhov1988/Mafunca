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
    'TResultM',
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
class TResultM(Generic[T, E]):
    """Container for a composite value of the form 'Result[Maybe[T], E]'"""
    inner: Result[Maybe[T], E]

    @staticmethod
    def just(value: T) -> 'TResultM[T, Never]':
        return TResultM(Ok(Just(value)))

    @staticmethod
    def nothing() -> 'TResultM[T, Never]':
        return TResultM(Ok(Nothing()))

    @staticmethod
    def error(error: E) -> 'TResultM[Never, E]':
        return TResultM(Err(error))

    @staticmethod
    def wrap_maybe(maybe: Maybe[T]) -> 'TResultM[T, Never]':
        return TResultM(Ok(maybe))

    @staticmethod
    def wrap_result(result: Result[T, E]) -> 'TResultM[T, E]':
        if isinstance(result, Err):
            return TResultM(result)
        return TResultM(Ok(Just(result.value)))

    @property
    def is_just(self) -> bool:
        inner = self.inner
        return isinstance(inner, Ok) and inner.value.is_just

    @property
    def is_nothing(self) -> bool:
        inner = self.inner
        return isinstance(inner, Ok) and inner.value.is_nothing

    @property
    def is_error(self) -> bool:
        return self.inner.is_error

    def map(self, fn: Callable[[T], R]) -> 'TResultM[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map', fn)
        if isinstance(self.inner, Err):
            return cast(TResultM[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(TResultM[R, E], self)
        value = fn(maybe.value)
        return TResultM(Ok(Just(value)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'TResultM[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_maybe', fn)
        if isinstance(self.inner, Err):
            return cast(TResultM[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(TResultM[R, E], self)
        return TResultM.wrap_maybe(fn(maybe.value))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'TResultM[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_result', fn)
        if isinstance(self.inner, Err):
            return cast(TResultM[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(TResultM[R, E], self)
        return TResultM.wrap_result(fn(maybe.value))

    def bind(self, fn: Callable[[T], 'TResultM[R, E]']) -> 'TResultM[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'bind', fn)
        if isinstance(self.inner, Err):
            return cast(TResultM[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(TResultM[R, E], self)
        return fn(maybe.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'TResultM[T, NewE]':
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'map_error', fn)
        if isinstance(self.inner, Ok):
            return cast(TResultM[T, NewE], self)
        error = self.inner.error
        return TResultM(Err(fn(error)))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Err) or isinstance(inner.value, Nothing):
            return alter
        return inner.value.value

    def unfold(self, *, ok: Callable[[Maybe[T]], R], err: Callable[[E], R]) -> R:
        """:raises MonadError: if the passed function is marked as impure"""
        panic_on_impure(self.__class__.__name__, 'unfold', ok, err)
        if isinstance(self.inner, Err):
            return err(self.inner.error)
        return ok(self.inner.value)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_null(
        value: R,
        is_nullable: Callable[[R], bool] = lambda v: v is None
) -> TResultM[R, E]:
    """Wraps the result based on 'is_nullable' predicate."""
    return TResultM.nothing() if is_nullable(value) else TResultM.just(value)


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
        :raises MonadError: if the passed function is marked as impure
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, TResultM[R, Exception]]:
        panic_on_impure('result_transformer', 'from_try', fn)

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> TResultM[R, Exception]:
            try:
                return from_null(fn(*args, **kwargs), is_nullable)
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return TResultM.error(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: TResultM[Callable[[T], R], E], val: TResultM[T, E]) -> TResultM[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
        :raises MonadError: if the passed function is marked as impure
    """
    if isinstance(fn.inner, Err):
        return cast(TResultM[R, E], fn)
    if isinstance(fn.inner.value, Nothing):
        return cast(TResultM[R, E], fn)
    panic_on_impure('result_transformer', 'ap', fn.inner.value.value)
    if isinstance(val.inner, Err):
        return cast(TResultM[R, E], val)
    if isinstance(val.inner.value, Nothing):
        return cast(TResultM[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return TResultM.just(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: TResultM[A1, E],
        arg2: TResultM[A2, E]
) -> TResultM[R, E]:
    """
        For a function with two POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(TResultM.just(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: TResultM[A1, E],
        arg2: TResultM[A2, E],
        arg3: TResultM[A3, E]
) -> TResultM[R, E]:
    """
        For a function with three POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(TResultM.just(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: TResultM[A1, E],
        arg2: TResultM[A2, E],
        arg3: TResultM[A3, E],
        arg4: TResultM[A4, E],
) -> TResultM[R, E]:
    """
        For a function with four POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(ap(TResultM.just(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: TResultM[Any, E]) -> TResultM[Union[Callable, R], E]:
    """
       For a function with an arbitrary number of POSITIONAL arguments.
       Wraps the passed function in the container and applies the applicative method.

       ATTENTION. When an incomplete number of arguments is passed,
       a curried version with partially applied arguments will be returned.
       However, since each call curries the passed function,
       the partially applied arguments from the previous step are not preserved.
       :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    result = TResultM.just(curry(fn))
    for arg in args:
        result = ap(result, arg)
    return result
