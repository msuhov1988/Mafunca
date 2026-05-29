from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union, ParamSpec, Any

from mafunca.maybe import Just, Nothing, Maybe, ap as maybe_ap
from mafunca.result import Ok, Err, Result
from mafunca.specials import is_impure
from mafunca.curry import curry, Curry
from mafunca.common.exceptions import MonadError


def _panic_on_impure(monad: str, method: str, *funcs: Callable) -> None:
    for fn in funcs:
        if is_impure(fn):
            raise MonadError(monad, method, f"impure function '{fn}' can not be used")


T = TypeVar("T")
E = TypeVar("E")
NewE = TypeVar('NewE')
R = TypeVar("R")


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
        if result.is_error:
            return ResultMaybeT(result)
        return ResultMaybeT(Ok(Just(result.value)))

    @property
    def is_just(self) -> bool:
        inner = self.inner
        return inner.is_ok and inner.value.is_just

    @property
    def is_nothing(self) -> bool:
        inner = self.inner
        return inner.is_ok and inner.value.is_nothing

    @property
    def is_error(self) -> bool:
        return self.inner.is_error

    def map(self, fn: Callable[[T], R]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map', fn)
        if self.inner.is_error:
            return self
        maybe = self.inner.value
        if maybe.is_nothing:
            return self
        return ResultMaybeT(Ok(Just(fn(maybe.value))))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_maybe', fn)
        if self.inner.is_error:
            return self
        maybe = self.inner.value
        return ResultMaybeT.wrap_maybe(maybe.bind(fn))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_result', fn)
        if self.inner.is_error:
            return self
        maybe = self.inner.value
        if maybe.is_nothing:
            return self
        return ResultMaybeT.wrap_result(fn(maybe.value))

    def bind(self, fn: Callable[[T], 'ResultMaybeT[R, E]']) -> 'ResultMaybeT[R, E]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'bind', fn)
        if self.inner.is_error:
            return self
        maybe = self.inner.value
        if maybe.is_nothing:
            return self
        return fn(maybe.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'ResultMaybeT[T, NewE]':
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'map_error', fn)
        return ResultMaybeT(self.inner.map_error(fn))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if inner.is_error or inner.value.is_nothing:
            return alter
        return inner.value.value

    def unfold(self, *, ok: Callable[[Maybe[T]], R], err: Callable[[E], R]) -> R:
        """:raises MonadError: if the passed function is marked as impure"""
        _panic_on_impure(self.__class__.__name__, 'unfold', ok, err)
        if self.inner.is_error:
            return err(self.inner.error)
        return ok(self.inner.value)


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
ExcSubtype = TypeVar('ExcSubtype', bound=Exception)


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
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, ResultMaybeT[R, ExcSubtype]]:

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> ResultMaybeT[R, ExcSubtype]:
            try:
                return from_null(fn(*args, **kwargs), is_nullable)
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return ResultMaybeT.error(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: ResultMaybeT[Callable[[T], R], E], val: ResultMaybeT[T, E]) -> ResultMaybeT[R, E]:
    """Applies value enclosed in the container to a function also in the container"""
    if fn.inner.is_error:
        return fn
    if fn.inner.value.is_nothing:
        return fn
    if val.inner.is_error:
        return val
    return ResultMaybeT.wrap_maybe(maybe_ap(fn.inner.value, val.inner.value))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: ResultMaybeT[A1, E],
        arg2: ResultMaybeT[A2, E]
) -> ResultMaybeT[R, E]:
    """Wraps the passed function in the container and applies the applicative method"""
    return ap(
        ap(ResultMaybeT.just(lambda a: lambda b: fn(a, b)), arg1),
        arg2
    )


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: ResultMaybeT[A1, E],
        arg2: ResultMaybeT[A2, E],
        arg3: ResultMaybeT[A3, E]
) -> ResultMaybeT[R, E]:
    """Wraps the passed function in the container and applies the applicative method"""
    return ap(
        ap(
            ap(ResultMaybeT.just(lambda a: lambda b: lambda c: fn(a, b, c)), arg1),
            arg2
        ),
        arg3
    )


def lift(fn: Callable[..., R], *args: ResultMaybeT[Any, E]) -> ResultMaybeT[Union[Curry[R], R], E]:
    """
       Wraps the passed function in the container and applies the applicative method.
       If fewer arguments are passed than the function requires, it returns a curried version in the container
       that waits for the remaining arguments
    """
    result = ResultMaybeT.just(curry(fn) if not isinstance(fn, Curry) else fn)
    for arg in args:
        result = ap(result, arg)
    return result
