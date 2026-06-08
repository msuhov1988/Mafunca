from dataclasses import dataclass
from time import sleep
from collections.abc import Callable
from typing import Generic, TypeVar, Any, Union, cast

from mafunca.common._lazy_support import prime_catch, continuation_catch  # noqa
from mafunca.common._lazy_support import async_prime_catch, async_prime_thread_catch  # noqa
from mafunca.common._lazy_support import panic_on_violations, panic_on_coroutine  # noqa
from mafunca.result import Result, Ok, Err
from mafunca.common.side_support import Report


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
        return Continuation(self, lambda a: Pure(fn(a)), fn)

    def bind(self, fn: Callable[[A], 'Side[B]']) -> 'Side[B]':
        return Continuation(self, fn, fn)

    @staticmethod
    def pure(value: A) -> 'Side[A]':
        return Pure(value)

    @staticmethod
    def effect(fn: Callable[[], A]) -> 'Side[A]':
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
    entity, continuations = effect, list()
    while True:
        if isinstance(entity, Continuation):
            continuations.append(entity.next)
            entity = entity.current

        elif isinstance(entity, Prime):
            entity = Pure(entity.prime())

        elif isinstance(entity, Pure):
            if len(continuations) == 0:
                return cast(A, entity.value)
            cont = continuations.pop()
            entity = cont(entity.value)

        else:
            panic_on_violations(Side.__name__, 'side_run', entity)


def side_safe_run(effect: Side[A]) -> Result[A, Exception]:
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    entity, continuations = effect, list()
    while True:
        if isinstance(entity, Continuation):
            continuations.append(entity.next)
            entity = entity.current

        elif isinstance(entity, Prime):
            output, error = prime_catch(entity.prime)
            if error is not None:
                return cast(Result[A, Exception], Err(error))
            entity = Pure(output)

        elif isinstance(entity, Pure):
            if len(continuations) == 0:
                return cast(Result[A, Exception], Ok(entity.value))
            cont = continuations.pop()
            output, error = continuation_catch(cont, entity.value)
            if error is not None:
                return cast(Result[A, Exception], Err(error))
            entity = output

        else:
            panic_on_violations(Side.__name__, 'side_safe_run', entity)


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


def side_rebuild_run(effect: Side[A]) -> Report[Side[A]]:
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'.

        Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    entity, continuations, last_success = effect, list(), None
    while True:
        if isinstance(entity, Continuation):
            continuations.append((entity.next, entity.next_origin))
            entity = entity.current

        elif isinstance(entity, Prime):
            output, error = prime_catch(entity.prime)
            if error is not None:
                rest = _rebuild_from_prime(entity.prime, continuations)
                return cast(Report[Side[A]], Report(last_success, exception=error, faulty=entity.prime, remainder=rest))
            entity = Pure(output)

        elif isinstance(entity, Pure):
            if len(continuations) == 0:
                return cast(Report[Side[A]], Report(entity.value, exception=None, faulty=None, remainder=None))
            last_success = entity.value
            cont, cont_origin = continuations.pop()
            output, error = continuation_catch(cont, last_success)
            if error is not None:
                continuations.append((cont, cont_origin))
                rest = _rebuild_from_pure(last_success, continuations)
                return cast(Report[Side[A]], Report(last_success, exception=error, faulty=cont_origin, remainder=rest))
            entity = output

        else:
            panic_on_violations(Side.__name__, 'side_rebuild_run', entity)


def insist(effect: Side[A], attempts: int = 1, pause: Union[int, float] = 0) -> Report[Side[A]]:
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    chain, report = effect, Report(None, None, None, None)
    for _ in range(attempts):
        report = side_rebuild_run(chain)
        if not report.completed_successfully:
            chain = report.remainder
            sleep(pause)
            continue
        break
    return cast(Report[Side[A]], report)
