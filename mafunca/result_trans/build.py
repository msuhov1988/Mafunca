from dataclasses import dataclass
from collections.abc import Callable, Generator
from functools import wraps
from typing import TypeVar, TypeGuard, ParamSpec, Never, Generic, Any, cast

from mafunca.maybe.build import Just, Nothing, Maybe
from mafunca.result.build import Success, Fail, Result
from mafunca.common.exceptions import MonadError


__all__ = [
    "ResultMaybe",
    "success",
    "nothing",
    "fail",
    "lift_maybe",
    "lift_result",
    "is_success",
    "is_nothing",
    "is_fail",
    "from_null",
    "from_try",
    "Step",
    "step",
    "Do",
    "do",
]


T = TypeVar("T")
E = TypeVar("E")
R = TypeVar("R")
Args = ParamSpec('Args')


type ResultMaybe[T, E] = Result[Maybe[T], E]


def success(value: T) -> ResultMaybe[T, Never]:
    return Success(Just(value))


def nothing() -> ResultMaybe[Never, Never]:
    return Success(Nothing())


def fail(error: E) -> ResultMaybe[Never, E]:
    return Fail(error)


def lift_maybe(maybe: Maybe[T]) -> ResultMaybe[T, Never]:
    return Success(maybe)


def lift_result(result: Result[T, E]) -> ResultMaybe[T, E]:
    if isinstance(result, Fail):
        return result
    return Success(Just(result.value))


def is_success(result_m: ResultMaybe[T, E]) -> TypeGuard[Success[Just[T]]]:    
    return isinstance(result_m, Success) and isinstance(result_m.value, Just)


def is_nothing(result_m: ResultMaybe[T, E]) -> TypeGuard[Success[Nothing]]:
    return isinstance(result_m, Success) and isinstance(result_m.value, Nothing)


def is_fail(result_m: ResultMaybe[T, E]) -> TypeGuard[Fail[E]]:
    return isinstance(result_m, Fail)


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> ResultMaybe[R, Never]:    
    return Success(Nothing() if is_nullable(value) else Just(value))


def from_try(fn: Callable[Args, R]) -> Callable[Args, ResultMaybe[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
    """  
    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> ResultMaybe[R, Exception]:
        try:
            return Success(Just(fn(*args, **kwargs)))
        except Exception as err:
            return Fail(err)

    return wraps(fn)(from_try_inner)


@dataclass(frozen=True, slots=True)
class Step(Generic[T, E]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: ResultMaybe[T, E]

    def __iter__(self) -> Generator[ResultMaybe[T, E], T, T]:
        if isinstance(self.for_yield, Fail):
            _ = yield self.for_yield
            raise MonadError(
                monad=f'{type(self).__module__}.{type(self).__qualname__}',
                method='__iter__',
                message='library failure(an unreachable instruction has been reached)'
            )
        maybe = self.for_yield.value
        if isinstance(maybe, Nothing):
            _ = yield self.for_yield
            raise MonadError(
                monad=f'{type(self).__module__}.{type(self).__qualname__}',
                method='__iter__',
                message='library failure(an unreachable instruction has been reached)'
            )        
        return (yield self.for_yield)
        


def step(for_yield: ResultMaybe[T, E]) -> Step[T, E]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


# a shorter typealias containing all the essential details
# because the types of intermediate results are derived from r = yield from Step(...)
type Do[R, E] = Generator[ResultMaybe[Any, E], Any, R]


def do(fn: Callable[Args, Do[R, E]]) -> Callable[Args, ResultMaybe[R, E]]:
    """
        Decorates a generator function implementing a ``ResultMaybe`` computations.

        Unwraps successfull ``Step`` values and propagates the first "bad branch".
    """
    wokflow = fn

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> ResultMaybe[R, E]:
        gen = None
        try:
            gen = wokflow(*args, **kwargs) 
            try:           
                result = next(gen)            
            except StopIteration as err:                
                return cast(ResultMaybe[R, E], Success(Just(err.value)))         

            while True: 
                if isinstance(result, Fail):
                    return result
                maybe = result.value
                if isinstance(maybe, Nothing):
                    return cast(ResultMaybe[R, E], result)
                value = maybe.value                            
                try:                    
                    result = gen.send(value)                
                except StopIteration as err:
                    return cast(ResultMaybe[R, E], Success(Just(err.value))) 
        finally:            
            if gen is not None:
                gen.close()

    return do_inner
