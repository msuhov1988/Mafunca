from typing import TypeVar, TypeAlias, Generic, Union, Optional, List, Tuple, Any, Never
from collections.abc import Callable, Awaitable
import asyncio

from mafunca.triple import TUtils, Left, Nothing
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError
import mafunca.common._resilient_specs as specs # noqa


__all__ = ['of', 'from_result', 'unit', 'insist', 'Resilient', 'DefaultBad']


_Exception = TypeVar('_Exception', bound=Exception)
_Ok = TypeVar('_Ok')
_Result = TypeVar('_Result')
_AwaitableOk = Union[Awaitable[_Ok], _Ok]
_AwaitableResult = Union[Awaitable[_Result], _Result]


DefaultBad = Union[Left, Nothing, Uncaught]
_Bad = TypeVar('_Bad', bound=DefaultBad)
_NewBad = TypeVar('_NewBad', bound=DefaultBad)
_AwaitableBad = Union[Awaitable[_Bad], _Bad]
_AwaitableNewBad = Union[Awaitable[_NewBad], _NewBad]

_PrimeEffect: TypeAlias = Callable[[], Union[_Ok, _Bad, Awaitable[_Ok], Awaitable[_Bad]]]
_ContEffect: TypeAlias = Callable[[Any], Union[_Ok, _Bad, Awaitable[_Ok], Awaitable[_Bad]]]
_Effect = Union[_PrimeEffect, _ContEffect]

_AwaitableSelf: TypeAlias = Union[Awaitable['Resilient[_Result, _NewBad]'], 'Resilient[_Result, _NewBad]']


async def _execute_prime(fn):
    """
       Execute prime effect from chain with catching errors.
       :raises MonadError: MonadError is not suppressed
    """
    try:
        return await specs.maybe_await(fn())
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


async def _execute_continuation(fn, value):
    """
        Execute continuation effect(wrapped in a special closure) from chain with catching errors.
        :raises MonadError: MonadError is not suppressed
    """

    try:
        return await fn(value)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _make_effect(val):
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


class Resilient(Generic[_Ok, _Bad]):
    __slots__ = ('_effect', '_past')

    def __init__(self, effect: _Effect, past: Optional['Resilient[Any, Any]'] = None):
        self._effect = effect
        self._past = past

    @property
    def effect(self) -> _Effect:
        return self._effect

    def chain(
        self,
        fn: Callable[[_Ok], Union[_AwaitableSelf, _AwaitableResult, _AwaitableNewBad]]
    ) -> 'Resilient[_Result, Union[_Bad, _NewBad]]':
        """Combines the logic of both 'map' and 'bind' in regular monads"""
        return self.__class__(specs.continuer(fn, bad_evaluator=TUtils.is_bad), past=self)

    def catch(
        self,
        fn: Callable[[_Exception], Union[_AwaitableSelf, _AwaitableResult, _AwaitableNewBad]]
    ) -> 'Resilient[_Result, Union[_Bad, _NewBad]]':
        """Handles errors(Exception heirs) that occurred earlier in the chain."""
        return self.__class__(specs.catcher(fn), past=self)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'Resilient[_Ok, _Bad]':
        """Guaranteed to execute the function-parameter, similar to try finally."""
        return self.__class__(specs.ensurer(fn), past=self)

    def _unwind(self) -> Tuple[_Effect, List[_Effect]]:
        """For inner usage only. Unwinding the chain to the first effect."""
        prime, continuations = None, []
        current, cls = self, self.__class__
        while True:
            previous = current._past  # noqa
            if not isinstance(previous, cls):
                prime = current.effect
                break
            continuations.append(current.effect)
            current = previous
        return prime, continuations

    async def _launch(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None
    ) -> Report[Union[_Ok, _Bad], Optional['Resilient[Any, Any]']]:
        cls = self.__class__
        first_effect, cons = self._unwind()
        result = await _execute_prime(first_effect)
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            return Report(result, chain_from_failure=self, faulty=first_effect, last_success=None)

        restored, faulty, last_success = None, None, result if rebuild else None
        first_index, last_index = specs.get_indexes_for_execution(steps, inverted_cons=cons)
        for i in range(first_index, last_index, -1):
            result_new = await _execute_continuation(cons[i], result)
            restored_new, faulty_new, last_success_new = None, None, None
            if isinstance(result_new, cls):
                report = await result_new.run(rebuild=rebuild)
                result_new, restored_new = report.result, report.chain_from_failure
                faulty_new, last_success_new = report.faulty, report.last_success

            if rebuild:
                if restored_new:
                    # if we're in this branch, it's the first failure!
                    restored, faulty, last_success = restored_new, faulty_new, last_success_new
                elif isinstance(result_new, Uncaught) or TUtils.is_bad(result_new):
                    if restored is None:
                        prime = cls(_make_effect(result))
                        restored, faulty = cls(cons[i], past=prime), specs.get_origin(cons[i])
                        last_success = result
                    else:
                        restored = cls(cons[i], past=restored)
                else:
                    restored, faulty, last_success = None, None, result_new
            result = result_new

        return Report(result, chain_from_failure=restored, faulty=faulty, last_success=last_success)

    async def run(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None,
        delay: Optional[Union[int, float]] = None
    ) -> Report[Union[_Ok, _Bad], Optional['Resilient[Any, Any]']]:
        """
            Async - starts the chain.
            :arg rebuild: restore the shortened chain(on failure) and identify the source of the failure
            :arg steps: positive integer(optional), number of steps for partial execution
            :arg delay: seconds, limit the amount of time spent waiting on execution
            :raises MonadError: violations of monadic contracts
            :raises TimeoutError: delay is not None and the waiting time has been exceeded.
        """
        if delay is None:
            return await self._launch(rebuild=rebuild, steps=steps)
        else:
            async with asyncio.timeout(delay=delay):
                return await self._launch(rebuild=rebuild, steps=steps)

    def to_task(self, rebuild: bool = False) -> asyncio.Task:
        """Wrap the chain starter method into a Task"""
        return asyncio.create_task(self._launch(rebuild=rebuild))


def of(value: _Ok) -> Resilient[_Ok, Never]:
    """Lazy monad for resilient async effects. Can accept both async and sync functions."""
    return Resilient(lambda: value)


def from_result(value: Union[_Ok, _Bad]) -> Resilient[_Ok, _Bad]:
    """Lazy monad for resilient async effects. Can accept both async and sync functions."""
    return Resilient(lambda: value)


def unit(fn: Callable[[], Union[Awaitable[_Ok], _Ok, Awaitable[_Bad], _Bad]]) -> Resilient[_Ok, _Bad]:
    """Lazy monad for resilient async effects. Can accept both async and sync functions."""
    return Resilient(fn)


async def insist(
        resilient: Resilient[_Ok, _Bad],
        attempts: int = 1,
        delay_for_attempt: Union[int, float] = None,
        pause_between: Union[int, float] = 0
) -> Report[Union[_Ok, _Bad], Optional[Resilient]]:
    """
        Makes 'attempts' with 'delay_for_attempt' to execute a 'resilient' chain
        with 'pause_between' intervals between them
    """
    chain, report = resilient, Report(None, resilient, None, None)

    for _ in range(attempts):
        if delay_for_attempt is None:
            report = await chain.run(rebuild=True)
        else:
            try:
                async with asyncio.timeout(delay=delay_for_attempt):
                    report = await chain.run(rebuild=True)
            except TimeoutError:
                await asyncio.sleep(pause_between)
                continue

        if not report.is_ok:
            chain = report.chain_from_failure
            await asyncio.sleep(pause_between)
            continue
        return report

    return report
