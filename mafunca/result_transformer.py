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
    'ResultMaybeT',
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
class ResultMaybeT(Generic[T, E]):
    """Container for a composite value of the form 'Result[Maybe[T], E]'"""
    inner: Result[Maybe[T], E]

    @staticmethod
    def just(value: T) -> 'ResultMaybeT[T, E]':
        return ResultMaybeT(Ok(Just(value)))

    @staticmethod
    def nothing() -> 'ResultMaybeT[T, E]':
        return ResultMaybeT(Ok(Nothing()))

    @staticmethod
    def error(error: E) -> 'ResultMaybeT[T, E]':
        return ResultMaybeT(Err(error))

    @staticmethod
    def wrap_maybe(maybe: Maybe[T]) -> 'ResultMaybeT[T, E]':
        return ResultMaybeT(Ok(maybe))

    @staticmethod
    def wrap_result(result: Result[T, E]) -> 'ResultMaybeT[T, E]':
        if isinstance(result, Err):
            return ResultMaybeT(result)
        return ResultMaybeT(Ok(Just(result.value)))

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

    def map(self, fn: Callable[[T], R]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        if isinstance(self.inner, Err):
            return cast(ResultMaybeT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultMaybeT[R, E], self)
        value = fn(maybe.value)
        return ResultMaybeT(Ok(Just(value)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_maybe', fn)
        if isinstance(self.inner, Err):
            return cast(ResultMaybeT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultMaybeT[R, E], self)
        return ResultMaybeT.wrap_maybe(fn(maybe.value))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_result', fn)
        if isinstance(self.inner, Err):
            return cast(ResultMaybeT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultMaybeT[R, E], self)
        return ResultMaybeT.wrap_result(fn(maybe.value))

    def bind(self, fn: Callable[[T], 'ResultMaybeT[R, E]']) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        if isinstance(self.inner, Err):
            return cast(ResultMaybeT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultMaybeT[R, E], self)
        return fn(maybe.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'ResultMaybeT[T, NewE]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_error', fn)
        if isinstance(self.inner, Ok):
            return cast(ResultMaybeT[T, NewE], self)
        error = self.inner.error
        return ResultMaybeT(Err(fn(error)))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Err) or isinstance(inner.value, Nothing):
            return alter
        return inner.value.value

    def unfold(self, *, ok: Callable[[Maybe[T]], R], err: Callable[[E], R]) -> R:
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', ok, err)
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
) -> ResultMaybeT[R, E]:
    """Wraps the result based on 'is_nullable' predicate."""
    return ResultMaybeT.nothing() if is_nullable(value) else ResultMaybeT.just(value)


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
        :raises MonadError: if the passed function is marked as impure
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, ResultMaybeT[R, Exception]]:
        _panic_on_impure('result_transformer', 'from_try', fn)

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> ResultMaybeT[R, Exception]:
            try:
                return from_null(fn(*args, **kwargs), is_nullable)
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return ResultMaybeT.error(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: ResultMaybeT[Callable[[T], R], E], val: ResultMaybeT[T, E]) -> ResultMaybeT[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
        :raises MonadError: if the passed function is marked as impure
    """
    if isinstance(fn.inner, Err):
        return cast(ResultMaybeT[R, E], fn)
    if isinstance(fn.inner.value, Nothing):
        return cast(ResultMaybeT[R, E], fn)
    _panic_on_impure('result_transformer', 'ap', fn.inner.value.value)
    if isinstance(val.inner, Err):
        return cast(ResultMaybeT[R, E], val)
    if isinstance(val.inner.value, Nothing):
        return cast(ResultMaybeT[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return ResultMaybeT.just(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: ResultMaybeT[A1, E],
        arg2: ResultMaybeT[A2, E]
) -> ResultMaybeT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ResultMaybeT.just(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: ResultMaybeT[A1, E],
        arg2: ResultMaybeT[A2, E],
        arg3: ResultMaybeT[A3, E]
) -> ResultMaybeT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(ResultMaybeT.just(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: ResultMaybeT[A1, E],
        arg2: ResultMaybeT[A2, E],
        arg3: ResultMaybeT[A3, E],
        arg4: ResultMaybeT[A4, E],
) -> ResultMaybeT[R, E]:
    """
        Wraps the passed function in the container and applies the applicative method
        :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    return ap(ap(ap(ap(ResultMaybeT.just(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: ResultMaybeT[Any, E]) -> ResultMaybeT[Union[Curry[R], R], E]:
    """
       Wraps the passed function in the container and applies the applicative method.
       If fewer arguments are passed than the function requires, it returns a curried version in the container
       that waits for the remaining arguments
       :raises MonadError: from the underlying function/method if passed function is marked as impure
    """
    result = ResultMaybeT.just(curry(fn) if not isinstance(fn, Curry) else fn)
    for arg in args:
        result = ap(result, arg)
    return result
