from typing import TypeVar, TypeAlias, Generic, Union, Optional, List, Tuple, Any, Never
from collections.abc import Callable
from time import sleep

from mafunca.triple import TUtils, Left, Nothing
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError
import mafunca.common._panics as panics  # noqa
import mafunca.common._resilient_specs as specs # noqa


__all__ = ['of', 'from_result', 'unit', 'insist', 'ResilientSync', 'DefaultBad']


_Exception = TypeVar('_Exception', bound=Exception)
_Ok = TypeVar('_Ok')
_Result = TypeVar('_Result')


DefaultBad = Union[Left, Nothing, Uncaught]
_Bad = TypeVar('_Bad', bound=DefaultBad)
_NewBad = TypeVar('_NewBad', bound=DefaultBad)

_PrimeEffect: TypeAlias = Callable[[], Union[_Ok, _Bad]]
_ContEffect: TypeAlias = Callable[[Any], Union[_Ok, _Bad]]
_Effect = Union[_PrimeEffect, _ContEffect]


def _execute_prime(fn):
    """
       Execute prime effect from chain with catching errors.
       :raises MonadError: MonadError is not suppressed
    """
    try:
        return fn()
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _execute_continuation(fn, value):
    """
        Execute continuation effect from chain with catching errors.
        :raises MonadError: MonadError is not suppressed
    """
    try:
        return fn(value)
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _make_effect(val):
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


class ResilientSync(Generic[_Ok, _Bad]):
    __slots__ = ('_effect', '_past')

    def __init__(self, effect: _Effect, past: Optional['ResilientSync[Any, Any]'] = None):
        panics.on_coroutine(effect, monad_name=self.__class__.__name__, method='__init__')
        self._effect = effect
        self._past = past

    @property
    def effect(self) -> _Effect:
        return self._effect

    def chain(
        self,
        fn: Callable[[_Ok], Union['ResilientSync[_Result, _NewBad]', _Result, _NewBad]]
    ) -> 'ResilientSync[_Result, Union[_Bad, _NewBad]]':
        """
            Combines the logic of both 'map' and 'bind' in regular monads.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='chain')
        return self.__class__(specs.continuer_sync(fn, bad_evaluator=TUtils.is_bad), past=self)

    def catch(
        self,
        fn: Callable[[_Exception], Union['ResilientSync[_Result, _NewBad]', _Result, _NewBad]]
    ) -> 'ResilientSync[_Result, Union[_Bad, _NewBad]]':
        """
            Handles errors(Exception heirs) that occurred earlier in the chain.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='catch')
        return self.__class__(specs.catcher_sync(fn), past=self)

    def ensure(self, fn: Callable[[], None]) -> 'ResilientSync[_Ok, _Bad]':
        """
            Guaranteed to execute the function-parameter, similar to try finally.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='ensure')
        return self.__class__(specs.ensurer_sync(fn), past=self)

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

    def run(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None
    ) -> Report[Union[_Ok, _Bad], Optional['ResilientSync[Any, Any]']]:
        """
            Starts the chain
            :arg rebuild: restore the shortened chain(on failure) and identify the source of the failure
            :arg steps: positive integer(optional), number of steps for partial execution
            :raises MonadError: violations of monadic contracts
        """
        cls = self.__class__
        first_effect, cons = self._unwind()
        result = _execute_prime(first_effect)
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            return Report(result, chain_from_failure=self, faulty=first_effect, last_success=None)

        restored, faulty, last_success = None, None, result if rebuild else None
        first_index, last_index = specs.get_indexes_for_execution(steps, inverted_cons=cons)
        for i in range(first_index, last_index, -1):
            result_new = _execute_continuation(cons[i], result)
            restored_new, faulty_new, last_success_new = None, None, None
            if isinstance(result_new, cls):
                report = result_new.run(rebuild=rebuild)
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


def of(value: _Ok) -> ResilientSync[_Ok, Never]:
    """Lazy monad for resilient SYNC ONLY effects."""
    return ResilientSync(lambda: value)


def from_result(value: Union[_Ok, _Bad]) -> ResilientSync[_Ok, _Bad]:
    """Lazy monad for resilient SYNC ONLY effects."""
    return ResilientSync(lambda: value)


def unit(fn: Callable[[], Union[_Ok, _Bad]]) -> ResilientSync[_Ok, _Bad]:
    """Lazy monad for resilient SYNC ONLY effects."""
    return ResilientSync(fn)


def insist(
        resilient: ResilientSync[_Ok, _Bad],
        attempts: int = 1,
        pause_between: Union[int, float] = 0
) -> Report[Union[_Ok, _Bad], Optional[ResilientSync]]:
    """Makes 'attempts' to execute a 'resilient' chain with 'pause_between' intervals between them"""
    chain, report = resilient, Report(None, None, None, None)

    for _ in range(attempts):
        report = chain.run(rebuild=True)
        if not report.is_ok:
            chain = report.chain_from_failure
            sleep(pause_between)
            continue
        return report

    return report
