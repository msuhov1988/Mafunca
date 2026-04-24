from typing import TypeVar, Generic, Union, Optional, List, Any, Never
from collections.abc import Callable, Awaitable
import inspect
import asyncio

from mafunca.triple import TUtils, Left, Nothing
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError
import mafunca.common._resilient_specs as specs # noqa


__all__ = ['of', 'unit', 'insist', 'Resilient', 'DefaultBad']


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


def _unwind(persist: 'Resilient') -> List[Callable]:
    """Unwinding the chain to the first effect"""
    current, effects = persist, []
    while isinstance(current, Resilient):
        effects.append(current.effect)
        current = current.past
    return effects


async def _execute(fn, value=None):
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
        :raises MonadError: panics on coroutine function
    """
    params = inspect.signature(fn).parameters
    try:
        if len(params) == 0:
            return await specs.maybe_await(fn())   # first effect maybe sync or async
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

    def __init__(
        self,
        effect: Callable[..., Union[_AwaitableOk, _AwaitableBad]],
        past: Optional['Resilient[Any, Any]'] = None
    ):
        self._effect = effect
        self._past = past

    @property
    def effect(self) -> Callable[..., Union[_AwaitableOk, _AwaitableBad]]:
        return self._effect

    @property
    def past(self) -> 'Resilient[Any, Any]':
        return self._past

    def chain(
        self,
        fn: Callable[[_Ok], Union['Resilient[_Result, _NewBad]', _AwaitableResult, _AwaitableNewBad]]
    ) -> 'Resilient[_Result, Union[_Bad, _NewBad]]':
        """Combines the logic of both 'map' and 'bind' in regular monads"""
        return self.__class__(specs.continuer(fn, bad_evaluator=TUtils.is_bad), past=self)

    def catch(
        self,
        fn: Callable[[_Exception], Union['Resilient[_Result, _NewBad]', _AwaitableResult, _AwaitableNewBad]]
    ) -> 'Resilient[_Result, Union[_Bad, _NewBad]]':
        """Handles errors(Exception heirs) that occurred earlier in the chain."""
        return self.__class__(specs.catcher(fn), past=self)

    def ensure(self, fn: Callable[[], Union[Awaitable[None], None]]) -> 'Resilient[_Ok, _Bad]':
        """Guaranteed to execute the function-parameter, similar to try finally."""
        return self.__class__(specs.ensurer(fn), past=self)

    async def _launch(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None
    ) -> Report[_Ok, Optional['Resilient[Any, Any]']]:
        result, restored, faulty, last_success = None, None, None, None
        cls = self.__class__
        funcs = _unwind(persist=self)
        first_index, last_index = specs.get_indexes_for_execution(steps, inverted_funcs=funcs)
        for i in range(first_index, last_index, -1):
            result_new = await _execute(funcs[i], result)  # since the first func has no params, we can safely pass None
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
                        restored, faulty = cls(funcs[i], past=prime), specs.get_origin(funcs[i])
                        last_success = result
                    else:
                        restored = cls(funcs[i], past=restored)
                else:
                    restored, faulty, last_success = None, None, result_new
            result = result_new

        return Report(result, chain_from_failure=restored, faulty=faulty, last_success=last_success)

    async def run(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None,
        delay: Optional[Union[int, float]] = None
    ) -> Report[_Ok, Optional['Resilient[Any, Any]']]:
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
    """
        Lazy monad for resilient async effects.
        Can accept both async and sync functions.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return Resilient(lambda: value)


def unit(fn: Callable[[], Union[Awaitable[_Ok], _Ok, _Bad]]) -> Resilient[_Ok, _Bad]:
    """
        Lazy monad for resilient async effects.
        Can accept both async and sync functions.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return Resilient(fn)


async def insist(
        resilient: Resilient[_Ok, _Bad],
        attempts: int = 1,
        delay_for_attempt: Union[int, float] = None,
        pause_between: Union[int, float] = 0
) -> Report[_Ok, Optional[Resilient]]:
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
