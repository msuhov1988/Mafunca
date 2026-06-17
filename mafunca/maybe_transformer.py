from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union, ParamSpec, cast, Any, Never

from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Ok, Err, Result
from mafunca.curry import curry2, curry3, curry4, curry
from mafunca.common.exceptions import MonadError


__all__ = [
    'MaybeT',
    'from_null',
    'from_try',
    'ok_of',
    'error_of',
    'nothing_of',
    'maybe_of',
    'result_of',
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


@dataclass(frozen=True, slots=True, repr=True)
class MaybeT(Generic[T, E]):
    """Container for a composite value of the form 'Maybe[Result[T, E]]'"""
    inner: Union[Just[Union[Ok[T], Err[E]]], Nothing]

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

    def map(self, fn: Callable[[T], R]) -> 'MaybeT[R, E]':
        return MaybeT(self.inner.map(lambda result: result.map(fn)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'MaybeT[R, E]':
        if isinstance(self.inner, Nothing):
            return cast(MaybeT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeT[R, E], self)
        maybe = fn(result.value)
        if isinstance(maybe, Nothing):
            return MaybeT(maybe)
        return MaybeT(Just(Ok(maybe.value)))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'MaybeT[R, E]':
        return MaybeT(self.inner.map(lambda result: result.bind(fn)))

    def bind(self, fn: Callable[[T], 'MaybeT[R, E]']) -> 'MaybeT[R, E]':
        if isinstance(self.inner, Nothing):
            return cast(MaybeT[R, E], self)
        result = self.inner.value
        if isinstance(result, Err):
            return cast(MaybeT[R, E], self)
        return fn(result.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'MaybeT[T, NewE]':
        return MaybeT(self.inner.map(lambda result: result.map_error(fn)))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Nothing) or isinstance(inner.value, Err):
            return alter
        return inner.value.value

    def unfold(self, *, just: Callable[[Result[T, E]], R], nothing: Callable[[], R]) -> R:
        if isinstance(self.inner, Nothing):
            return nothing()
        return just(self.inner.value)


def ok_of(value: T) -> MaybeT[T, Never]:
    return MaybeT(Just(Ok(value)))


def error_of(error: E) -> MaybeT[Never, E]:
    return MaybeT(Just(Err(error)))


def nothing_of() -> MaybeT[Never, Never]:
    return MaybeT(Nothing())


def maybe_of(maybe: Maybe[T]) -> MaybeT[T, Never]:
    if isinstance(maybe, Nothing):
        return MaybeT(maybe)
    return MaybeT(Just(Ok(maybe.value)))


def result_of(result: Result[T, E]) -> MaybeT[T, E]:
    return MaybeT(Just(result))


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_null(is_nullable: Callable[[R], bool] = lambda v: v is None) -> Callable[[R], MaybeT[R, Never]]:
    """Closure. Wraps the result based on 'is_nullable' predicate."""
    def from_null_inner(value: R) -> MaybeT[R, Never]:
        return nothing_of() if is_nullable(value) else ok_of(value)

    return from_null_inner


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, MaybeT[R, Exception]]:

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> MaybeT[R, Exception]:
            try:
                return from_null(is_nullable)(fn(*args, **kwargs))
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return error_of(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: MaybeT[Callable[[T], R], E], val: MaybeT[T, E]) -> MaybeT[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
    """
    if isinstance(fn.inner, Nothing):
        return cast(MaybeT[R, E], fn)
    if isinstance(fn.inner.value, Err):
        return cast(MaybeT[R, E], fn)
    if isinstance(val.inner, Nothing):
        return cast(MaybeT[R, E], val)
    if isinstance(val.inner.value, Err):
        return cast(MaybeT[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return ok_of(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: MaybeT[A1, E],
        arg2: MaybeT[A2, E]
) -> MaybeT[R, E]:
    """
        For a function with two POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
    """
    return ap(ap(ok_of(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: MaybeT[A1, E],
        arg2: MaybeT[A2, E],
        arg3: MaybeT[A3, E]
) -> MaybeT[R, E]:
    """
        For a function with three POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
    """
    return ap(ap(ap(ok_of(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: MaybeT[A1, E],
        arg2: MaybeT[A2, E],
        arg3: MaybeT[A3, E],
        arg4: MaybeT[A4, E]
) -> MaybeT[R, E]:
    """
        For a function with four POSITIONAL arguments.
        Wraps the passed function in the container and applies the applicative method
    """
    return ap(ap(ap(ap(ok_of(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: MaybeT[Any, E]) -> MaybeT[Union[Callable, R], E]:
    """
       For a function with an arbitrary number of POSITIONAL arguments.
       Wraps the passed function in the container and applies the applicative method.

       ATTENTION. When an incomplete number of arguments is passed,
       a curried version with partially applied arguments will be returned.
       However, since each call curries the passed function,
       the partially applied arguments from the previous step are not preserved.
    """
    result = ok_of(curry(fn))
    for arg in args:
        result = ap(result, arg)
    return result
