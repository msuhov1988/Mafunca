from dataclasses import dataclass
from collections.abc import Callable, Generator
from typing import TypeVar, Generic, TypeGuard, ParamSpec, Never, Any, cast

from mafunca.common.exceptions import MonadError


__all__ = [
    "Just",
    "Nothing",
    "Maybe",
    "just",
    "nothing",
    "is_just",
    "is_nothing",
    "from_null",
    "Step",
    "step",
    "Do",
    "do",
]


T_co = TypeVar("T_co", covariant=True)
T = TypeVar("T")
R = TypeVar("R")
Args = ParamSpec('Args')


@dataclass(frozen=True, slots=True)
class Just(Generic[T_co]):
    """A container for non-nullable value"""
    value: T_co


@dataclass(frozen=True, slots=True)
class Nothing:
    """A container representing the absence of a value"""
    pass


type Maybe[T] = Just[T] | Nothing


def just(value: T) -> Maybe[T]:
    return Just(value)


def nothing() -> Maybe[Never]:
    return Nothing()


def is_just(maybe: Maybe[T]) -> TypeGuard[Just[T]]:
    return True if isinstance(maybe, Just) else False


def is_nothing(maybe: Maybe[T]) -> TypeGuard[Nothing]:
    return True if isinstance(maybe, Nothing) else False


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> Maybe[R]:
    return Nothing() if is_nullable(value) else Just(value)


@dataclass(frozen=True, slots=True)
class Step(Generic[T]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: Maybe[T]

    def __iter__(self) -> Generator[Maybe[T], T, T]:
        if isinstance(self.for_yield, Just):
            return (yield self.for_yield)
        _ = yield self.for_yield
        raise MonadError(
            monad=f'{type(self).__module__}.{type(self).__qualname__}',
            method='__iter__',
            message='library failure(an unreachable instruction has been reached)'
        )


def step(for_yield: Maybe[T]) -> Step[T]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


# a shorter typealias containing all the essential details
# because the types of intermediate results are derived from r = yield from Step(...)
type Do[R] = Generator[Maybe[Any], Any, R]


def do(fn: Callable[Args, Do[R]]) -> Callable[Args, Maybe[R]]:
    """
        Decorates a generator function implementing a ``Maybe`` computations.

        Unwraps successfull ``Step`` values and propagates the first ``Nothing``.
    """
    wokflow = fn

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> Maybe[R]:
        gen = None
        try:
            gen = wokflow(*args, **kwargs)
            try:            
                result = next(gen)  
            except StopIteration as err:
                return cast(Maybe[R], Just(err.value))          

            while True:
                if isinstance(result, Nothing):
                    return result
                try:
                    result = gen.send(result.value)
                except StopIteration as err:
                    return cast(Maybe[R], Just(err.value))
        finally:
            if gen is not None:
                gen.close()

    return do_inner
