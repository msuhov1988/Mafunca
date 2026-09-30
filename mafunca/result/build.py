from dataclasses import dataclass
from collections.abc import Callable, Generator
from functools import wraps
from typing import TypeVar, Generic, TypeGuard, ParamSpec, Never, Any, cast

from mafunca.common.exceptions import MonadError


__all__ = [
    "Success",
    "Fail",
    "Result",
    "success",
    "fail",
    "is_success",
    "is_fail",
    "from_try",
    "Step",
    "step",
    "Do",
    "do",
]


T_co = TypeVar("T_co", covariant=True)
E_co = TypeVar("E_co", covariant=True)
T = TypeVar("T")
R = TypeVar("R")
E = TypeVar("E")
Args = ParamSpec('Args')


@dataclass(frozen=True, slots=True)
class Success(Generic[T_co]):
    """A container for a value representing a successful result"""
    value: T_co


@dataclass(frozen=True, slots=True)
class Fail(Generic[E_co]):
    """A container for a value representing an error"""
    error: E_co


type Result[T, E] = Success[T] | Fail[E]


def success(value: T) -> Result[T, Never]:
    return Success(value)


def fail(error: E) -> Result[Never, E]:
    return Fail(error)


def is_success(result: Result[T, E]) -> TypeGuard[Success[T]]:
    return True if isinstance(result, Success) else False


def is_fail(result: Result[T, E]) -> TypeGuard[Fail[E]]:
    return True if isinstance(result, Fail) else False


def from_try(fn: Callable[Args, R]) -> Callable[Args, Result[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'.
    """

    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> Result[R, Exception]:
        try:
            return Success(fn(*args, **kwargs))
        except Exception as err:
            return Fail(err)

    return wraps(fn)(from_try_inner)


@dataclass(frozen=True, slots=True)
class Step(Generic[T, E]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: Result[T, E]

    def __iter__(self) -> Generator[Result[T, E], T, T]:
        if isinstance(self.for_yield, Success):
            return (yield self.for_yield)
        _ = yield self.for_yield
        raise MonadError(
            monad=f'{type(self).__module__}.{type(self).__qualname__}',
            method='__iter__',
            message='library failure(an unreachable instruction has been reached)'
        )


def step(for_yield: Result[T, E]) -> Step[T, E]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


# a shorter typealias containing all the essential details
# because the types of intermediate results are derived from r = yield from Step(...)
type Do[R, E] = Generator[Result[Any, E], Any, R]


def do(fn: Callable[Args, Do[R, E]]) -> Callable[Args, Result[R, E]]:
    """
        Decorates a generator function implementing a ``Result`` computations.

        Unwraps successfull ``Step`` values and propagates the first failure.
    """
    wokflow = fn

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> Result[R, E]:
        gen = None
        try:
            gen = wokflow(*args, **kwargs) 
            try:           
                result = next(gen)  
            except StopIteration as err:                
                return cast(Result[R, E], Success(err.value))          

            while True:
                if isinstance(result, Fail):
                    return result
                try:
                    result = gen.send(result.value)
                except StopIteration as err:
                    return cast(Result[R, E], Success(err.value))
        finally:            
            if gen is not None:
                gen.close()

    return do_inner
