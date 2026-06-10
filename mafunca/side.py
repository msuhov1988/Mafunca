from dataclasses import dataclass
from contextlib import closing
from time import sleep
from collections.abc import Callable
from typing import Generic, TypeVar, Any, Union, cast

from mafunca.common.exceptions import MonadError
from mafunca._lazy_support import panic_on_violations, panic_on_coroutine  # noqa
from mafunca._lazy_support import runner, rebuild_runner, Yield, Return  # noqa
from mafunca.result import Result, Ok, Err
from mafunca.side_report import Report


__all__ = [
    "Side",
    "side_run",
    "side_safe_run",
    "side_rebuild_run",
    "insist"
]


A = TypeVar("A")
B = TypeVar("B")


class Side(Generic[A]):
    """
        A monad for SYNCHRONOUS ONLY effects.
        Lazy: not executed until the corresponding executor is called.
    """
    def map(self, fn: Callable[[A], B]) -> 'Side[B]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'map')
        return Continuation(self, lambda a: Pure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'Side[B]']) -> 'Side[B]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, self.__class__.__name__, 'bind')
        return Continuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'Side[A]':
        return Pure(value)

    @staticmethod
    def effect(fn: Callable[[], A]) -> 'Side[A]':
        """:raises MonadError: coroutine functions are not allowed"""
        panic_on_coroutine(fn, Side.__name__, 'effect')
        return Prime(fn)


@dataclass(frozen=True, slots=True, repr=True)
class Pure(Side[A]):
    value: A


@dataclass(frozen=True, slots=True, repr=True)
class Prime(Side[A]):
    prime: Callable[[], A]


@dataclass(frozen=True, slots=True, repr=True)
class Continuation(Side[B]):
    current: Side[Any]
    next: Callable[[Any], Side[B]]
    next_origin: Callable[[Any], Union[B, Side[B]]]


def side_run(effect: Side[A]) -> A:
    """
        Simple synchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    with closing(runner(effect, Pure, Continuation)) as gen:
        try:
            entity = next(gen)
            while True:
                if isinstance(entity, Prime):
                    entity = gen.send(Pure(entity.prime()))
                else:
                    panic_on_violations(Side.__name__, 'side runner method', entity)
        except StopIteration as finish:
            return cast(A, finish.value)


def side_safe_run(effect: Side[A]) -> Result[A, Exception]:
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    try:
        return cast(Result[A, Exception], Ok(side_run(effect)))
    except MonadError:
        raise
    except Exception as err:
        return cast(Result[A, Exception], Err(err))


def _rebuild_from_prime(prime, continuations) -> Side:
    effect = Side.effect(prime)

    while len(continuations) > 0:
        cont, cont_origin = continuations.pop()
        effect = Continuation(effect, cont, cont_origin)

    return effect


def _rebuild_from_pure(pure_val, continuations) -> Side:
    effect = Side.pure(pure_val)

    while len(continuations) > 0:
        cont, cont_origin = continuations.pop()
        effect = Continuation(effect, cont, cont_origin)

    return effect


def side_rebuild_run(effect: Side[A]) -> Report[Any, Side[A]]:
    """
       Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'.

       Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

       MonadError is not suppressed.
       :raises MonadError: violations of the contract
    """
    with closing(rebuild_runner(effect, Pure, Continuation)) as gen:
        try:
            yld: Yield = next(gen)
            entity, last_success, stack = yld.entity, yld.last_success, yld.stack
            while True:
                if isinstance(entity, Prime):
                    try:
                        pure_from_prime = Pure(entity.prime())
                    except MonadError:
                        raise
                    except Exception as error:
                        rest = _rebuild_from_prime(entity.prime, stack.copy())
                        return cast(Report[Any, Side[A]], Report(last_success, error, entity.prime, remainder=rest))
                    yld: Yield = gen.send(pure_from_prime)
                    entity, last_success, stack = yld.entity, yld.last_success, yld.stack
                else:
                    panic_on_violations(Side.__name__, 'side runner method', entity)
        except StopIteration as finish:
            rtn: Return = finish.value
            last_success, error, faulty, stack = rtn.last_success, rtn.error, rtn.faulty, rtn.stack
            rest = _rebuild_from_pure(last_success, stack.copy())
            return cast(Report[Any, Side[A]], Report(last_success, error, faulty, remainder=rest))


def insist(effect: Side[A], attempts: int = 1, pause: Union[int, float] = 0) -> Report[Any, Side[A]]:
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    chain, report = effect, Report(None, None, None, effect)
    for _ in range(attempts):
        report = side_rebuild_run(chain)
        if not report.completed_successfully:
            chain = report.remainder
            sleep(pause)
            continue
        break
    return cast(Report[Any, Side[A]], report)
