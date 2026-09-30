from dataclasses import dataclass
from collections.abc import Callable, Generator
from functools import wraps
from typing import TypeVar, TypeGuard, ParamSpec, Never, Generic, Any, cast

from mafunca.maybe.build import Just, Nothing, Maybe
from mafunca.result.build import Success, Fail, Result
from mafunca.common.exceptions import MonadError


__all__ = [
    "MaybeResult",
    "just",
    "nothing",
    "fail",
    "lift_maybe",
    "lift_result",
    "is_just",
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
E1 = TypeVar('E1')
E2 = TypeVar('E2')
R = TypeVar("R")
Args = ParamSpec('Args')


type MaybeResult[T, E] = Maybe[Result[T, E]]


def just(value: T) -> MaybeResult[T, Never]:
    return Just(Success(value))


def nothing() -> MaybeResult[Never, Never]:
    return Nothing()


def fail(error: E) -> MaybeResult[Never, E]:
    return Just(Fail(error))


def lift_maybe(maybe: Maybe[T]) -> MaybeResult[T, Never]:
    if isinstance(maybe, Nothing):
        return maybe
    return Just(Success(maybe.value))


def lift_result(result: Result[T, E]) -> MaybeResult[T, E]:    
    return Just(result)


def is_just(maybe_r: MaybeResult[T, E]) -> TypeGuard[Just[Success[T]]]:    
    return isinstance(maybe_r, Just) and isinstance(maybe_r.value, Success)


def is_nothing(maybe_r: MaybeResult[T, E]) -> TypeGuard[Nothing]:
    return isinstance(maybe_r, Nothing)


def is_fail(maybe_r: MaybeResult[T, E]) -> TypeGuard[Just[Fail[E]]]:
    return isinstance(maybe_r, Just) and isinstance(maybe_r.value, Fail)


def from_null(value: R, is_nullable: Callable[[R], bool] = lambda v: v is None) -> MaybeResult[R, Never]:    
    return Nothing() if is_nullable(value) else Just(Success(value))


def from_try(fn: Callable[Args, R]) -> Callable[Args, MaybeResult[R, Exception]]:
    """
        Decorator. Performs a function, catching possible errors - heirs of 'Exception'
        and wraps the result based on 'is_nullable' predicate.
    """  
    def from_try_inner(*args: Args.args, **kwargs: Args.kwargs) -> MaybeResult[R, Exception]:
        try:
            return Just(Success(fn(*args, **kwargs)))
        except Exception as err:
            return Just(Fail(err))

    return wraps(fn)(from_try_inner)


@dataclass(frozen=True, slots=True)
class Step(Generic[T, E]):
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    for_yield: MaybeResult[T, E]

    def __iter__(self) -> Generator[MaybeResult[T, E], T, T]:
        if isinstance(self.for_yield, Nothing):
            _ = yield self.for_yield
            raise MonadError(
                monad=f'{type(self).__module__}.{type(self).__qualname__}',
                method='__iter__',
                message='library failure(an unreachable instruction has been reached)'
            )
        result = self.for_yield.value
        if isinstance(result, Fail):
            _ = yield self.for_yield
            raise MonadError(
                monad=f'{type(self).__module__}.{type(self).__qualname__}',
                method='__iter__',
                message='library failure(an unreachable instruction has been reached)'
            )        
        return (yield self.for_yield)
        


def step(for_yield: MaybeResult[T, E]) -> Step[T, E]:
    """
        Represents a single computation step used with ``yield from`` in a ``@do`` block     
    """
    return Step(for_yield)


# a shorter typealias containing all the essential details
# because the types of intermediate results are derived from r = yield from Step(...)
type Do[R, E] = Generator[MaybeResult[Any, E], Any, R]


def do(fn: Callable[Args, Do[R, E]]) -> Callable[Args, MaybeResult[R, E]]:
    """
        Decorates a generator function implementing a ``MaybeResult`` computations.

        Unwraps successfull ``Step`` values and propagates the first "bad branch".
    """
    wokflow = fn

    def do_inner(*args: Args.args, **kwargs: Args.kwargs) -> MaybeResult[R, E]:
        gen = None
        try:
            gen = wokflow(*args, **kwargs) 
            try:           
                maybe = next(gen)            
            except StopIteration as err:                
                return cast(MaybeResult[R, E], Just(Success(err.value)))         

            while True: 
                if isinstance(maybe, Nothing):
                    return maybe
                result = maybe.value
                if isinstance(result, Fail):
                    return cast(MaybeResult[R, E], maybe)
                value = result.value                            
                try:                    
                    maybe = gen.send(value)                
                except StopIteration as err:
                    return cast(MaybeResult[R, E], Just(Success(err.value))) 
        finally:            
            if gen is not None:
                gen.close()

    return do_inner
