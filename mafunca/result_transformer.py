from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Generic, Union, ParamSpec, cast, Any, Never

from mafunca.maybe import Just, Nothing, Maybe
from mafunca.result import Ok, Err, Result
from mafunca.curry import curry2, curry3, curry4
from mafunca.common.exceptions import MonadError


__all__ = [
    'ResultT',
    'from_null',
    'from_try',
    'just_of',
    'nothing_of',
    'error_of',
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
class ResultT(Generic[T, E]):
    """Container for a composite value of the form 'Result[Maybe[T], E]'"""
    inner: Union[Ok[Union[Just[T], Nothing]], Err[E]]

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

    def map(self, fn: Callable[[T], R]) -> 'ResultT[R, E]':
        return ResultT(self.inner.map(lambda maybe: maybe.map(fn)))

    def map_maybe(self, fn: Callable[[T], Maybe[R]]) -> 'ResultT[R, E]':
        return ResultT(self.inner.map(lambda maybe: maybe.bind(fn)))

    def map_result(self, fn: Callable[[T], Result[R, E]]) -> 'ResultT[R, E]':
        if isinstance(self.inner, Err):
            return cast(ResultT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultT[R, E], self)
        result = fn(maybe.value)
        if isinstance(result, Err):
            return cast(ResultT[R, E], ResultT(result))
        return cast(ResultT[R, E], ResultT(Ok(Just(result.value))))

    def bind(self, fn: Callable[[T], 'ResultT[R, E]']) -> 'ResultT[R, E]':
        if isinstance(self.inner, Err):
            return cast(ResultT[R, E], self)
        maybe = self.inner.value
        if isinstance(maybe, Nothing):
            return cast(ResultT[R, E], self)
        return fn(maybe.value)

    def map_error(self, fn: Callable[[E], NewE]) -> 'ResultT[T, NewE]':
        return ResultT(self.inner.map_error(fn))

    def get_or_else(self, alter: T) -> T:
        inner = self.inner
        if isinstance(inner, Err) or isinstance(inner.value, Nothing):
            return alter
        return inner.value.value

    def unfold(self, *, ok: Callable[[Maybe[T]], R], err: Callable[[E], R]) -> R:
        if isinstance(self.inner, Err):
            return err(self.inner.error)
        return ok(self.inner.value)


def just_of(value: T) -> ResultT[T, Never]:
    return ResultT(Ok(Just(value)))


def nothing_of() -> ResultT[Never, Never]:
    return ResultT(Ok(Nothing()))


def error_of(error: E) -> ResultT[Never, E]:
    return ResultT(Err(error))


def maybe_of(maybe: Maybe[T]) -> ResultT[T, Never]:
    return ResultT(Ok(maybe))


def result_of(result: Result[T, E]) -> ResultT[T, E]:
    if isinstance(result, Err):
        return ResultT(result)
    return ResultT(Ok(Just(result.value)))


Args = ParamSpec('Args')
A1 = TypeVar("A1")
A2 = TypeVar("A2")
A3 = TypeVar("A3")
A4 = TypeVar("A4")


def from_null(is_nullable: Callable[[R], bool] = lambda v: v is None) -> Callable[[R], ResultT[R, Never]]:
    """Closure. Wraps the result based on 'is_nullable' predicate."""
    def from_null_inner(value: R) -> ResultT[R, Never]:
        return nothing_of() if is_nullable(value) else just_of(value)

    return from_null_inner


def from_try(is_nullable: Callable[[R], bool] = lambda v: v is None):
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
        'MonadError' is not suppressed.
    """
    def decorator(fn: Callable[Args, R]) -> Callable[Args, ResultT[R, Exception]]:

        def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> ResultT[R, Exception]:
            try:
                return from_null(is_nullable)(fn(*args, **kwargs))
            except Exception as err:
                if isinstance(err, MonadError):
                    raise err
                return error_of(err)

        return wraps(fn)(wrapper)

    return decorator


def ap(fn: ResultT[Callable[[T], R], E], val: ResultT[T, E]) -> ResultT[R, E]:
    """
        Applies value enclosed in the container to a function also in the container.
    """
    if isinstance(fn.inner, Err):
        return cast(ResultT[R, E], fn)
    if isinstance(fn.inner.value, Nothing):
        return cast(ResultT[R, E], fn)
    if isinstance(val.inner, Err):
        return cast(ResultT[R, E], val)
    if isinstance(val.inner.value, Nothing):
        return cast(ResultT[R, E], val)
    func = fn.inner.value.value
    arg = val.inner.value.value
    return just_of(func(arg))


def lift2(
        fn: Callable[[A1, A2], R],
        arg1: ResultT[A1, E],
        arg2: ResultT[A2, E]
) -> ResultT[R, E]:
    return ap(ap(just_of(curry2(fn)), arg1), arg2)


def lift3(
        fn: Callable[[A1, A2, A3], R],
        arg1: ResultT[A1, E],
        arg2: ResultT[A2, E],
        arg3: ResultT[A3, E]
) -> ResultT[R, E]:
    return ap(ap(ap(just_of(curry3(fn)), arg1), arg2), arg3)


def lift4(
        fn: Callable[[A1, A2, A3, A4], R],
        arg1: ResultT[A1, E],
        arg2: ResultT[A2, E],
        arg3: ResultT[A3, E],
        arg4: ResultT[A4, E],
) -> ResultT[R, E]:
    return ap(ap(ap(ap(just_of(curry4(fn)), arg1), arg2), arg3), arg4)


def lift(fn: Callable[..., R], *args: ResultT[Any, E]) -> ResultT[R, E]:
    unwrapped = list()
    for arg in args:
        if isinstance(arg.inner, Err):
            return arg
        if isinstance(arg.inner.value, Nothing):
            return arg
        unwrapped.append(arg.inner.value.value)
    return just_of(fn(*unwrapped))
