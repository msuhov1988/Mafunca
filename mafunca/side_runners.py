from contextlib import closing
from time import sleep
from typing import TypeVar, Union, Any, cast, overload

from mafunca.common.exceptions import MonadError
from mafunca._lazy_support import panic_on_violations
from mafunca._lazy_support import runner, rebuild_runner, Yield, Return, rebuild_from
from mafunca.result import Result, Ok, Err
from mafunca.side import Side, SideT
from mafunca.side import _Pure, _Effect, _Continuation  # noqa
from mafunca.side_rebuild_report import Report


__all__ = [
    "run",
    "run_safe",
    "run_rebuild",
    "insist",
]


A = TypeVar("A")
E = TypeVar("E")


@overload
def run(effect: SideT[A, E]) -> Result[A, E]: ...
@overload
def run(effect: Side[A]) -> A: ...


def run(effect):
    """
        Simple synchronous executor - just runs a chain.
        :raises MonadError: violations of the contract
    """
    eff = effect if isinstance(effect, Side) else effect.inner
    with closing(runner(eff, _Pure, _Continuation)) as gen:
        try:
            entity = next(gen)
            while True:
                if isinstance(entity, _Effect):
                    entity = gen.send(_Pure(entity.prime()))
                else:
                    panic_on_violations(Side.__name__, 'run', entity)
        except StopIteration as finish:
            return finish.value


@overload
def run_safe(effect: SideT[A, E]) -> Result[Result[A, E], Exception]: ...
@overload
def run_safe(effect: Side[A]) -> Result[A, Exception]: ...


def run_safe(effect):
    """
        Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'

        MonadError is not suppressed.
    """
    try:
        return Ok(run(effect))
    except MonadError:
        raise
    except Exception as err:
        return Err(err)


@overload
def run_rebuild(effect: SideT[A, E]) -> Report[Result[Any, E], SideT[A, E]]: ...
@overload
def run_rebuild(effect: Side[A]) -> Report[Any, Side[A]]: ...


def run_rebuild(effect):
    """
       Synchronous executor - runs a chain, catching possible errors - heirs of 'Exception'.

       Returns a special object that contains the last successful result, caught exception, and the unfinished steps.

       MonadError is not suppressed.
       :raises MonadError: violations of the contract
    """
    eff = effect if isinstance(effect, Side) else effect.inner
    with closing(rebuild_runner(eff, _Pure, _Continuation)) as gen:
        try:
            yld: Yield = next(gen)
            entity, last_success, stack = yld.entity, yld.last_success, yld.stack
            while True:
                if isinstance(entity, _Effect):
                    try:
                        pure_from_prime = _Pure(entity.prime())
                    except MonadError:
                        raise
                    except Exception as error:
                        rest = rebuild_from(entity, stack, _Continuation)
                        return cast(Report[Any, Side[A]], Report(last_success, error, entity.prime, remainder=rest))
                    yld: Yield = gen.send(pure_from_prime)
                    entity, last_success, stack = yld.entity, yld.last_success, yld.stack
                else:
                    panic_on_violations(Side.__name__, 'run_rebuild', entity)
        except StopIteration as finish:
            rtn: Return = finish.value
            last_success, error, faulty, stack = rtn.last_success, rtn.error, rtn.faulty, rtn.stack
            rest = rebuild_from(Side.pure(last_success), stack, _Continuation)
            return cast(Report[Any, Side[A]], Report(last_success, error, faulty, remainder=rest))


@overload
def insist(
        effect: SideT[A, E],
        attempts: int = 1,
        pause: Union[int, float] = 0
) -> Report[Result[Any, E], SideT[A, E]]: ...


@overload
def insist(
        effect: Side[A],
        attempts: int = 1,
        pause: Union[int, float] = 0
) -> Report[Any, Side[A]]: ...


def insist(effect, attempts=1, pause=0):
    """
        Makes 'attempts' to execute an effect with 'pause' intervals between them

        MonadError is not suppressed.
        :raises MonadError: violations of the contract
    """
    chain, report = effect, Report(None, None, None, effect)
    for _ in range(attempts):
        report = run_rebuild(chain)
        if not report.completed_successfully:
            chain = report.remainder
            sleep(pause)
            continue
        break
    return cast(Report[Any, Side[A]], report)
