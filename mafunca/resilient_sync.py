from typing import TypeVar, Generic, Union, Optional, List, Any, Never
import inspect
from collections.abc import Callable
from time import sleep

from mafunca.triple import TUtils, Left, Nothing
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError
import mafunca.common._panics as panics  # noqa
import mafunca.common._resilient_specs as specs # noqa

__all__ = ['of', 'unit', 'insist', 'ResilientSync']

_Exception = TypeVar('_Exception', bound=Exception)
_Ok = TypeVar('_Ok')
_Result = TypeVar('_Result')


_Bad = TypeVar('_Bad', bound=Union[Left, Nothing, Uncaught], default=Any)
_NewBad = TypeVar('_NewBad', bound=Union[Left, Nothing, Uncaught], default=Any)


def _unwind(persist: 'ResilientSync') -> List[Callable]:
    """Unwinding the chain to the first effect"""
    current, effects = persist, []
    while isinstance(current, ResilientSync):
        effects.append(current.effect)
        current = current.past
    return effects


def _execute(fn, value=None):
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
        :raises MonadError: panics on coroutine function
    """
    panics.on_coroutine(fn, monad_name='ResilientSync', method='run')
    params = inspect.signature(fn).parameters
    try:
        return fn() if len(params) == 0 else fn(value)
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _make_effect(val):
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


class ResilientSync(Generic[_Ok, _Bad]):
    __slots__ = ('_effect', '_past')

    def __init__(self, effect: Callable[..., Union[_Ok, _Bad]], past: Optional['ResilientSync[Any, Any]'] = None):
        panics.on_coroutine(effect, monad_name=self.__class__.__name__, method='__init__')
        self._effect = effect
        self._past = past

    @property
    def effect(self) -> Callable[..., Union[_Ok, _Bad]]:
        return self._effect

    @property
    def past(self) -> 'ResilientSync[Any, Any]':
        return self._past

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

    def run(
        self,
        rebuild: bool = False,
        steps: Optional[int] = None
    ) -> Report[_Ok, Optional['ResilientSync[Any, Any]']]:
        """
            Starts the chain
            :arg rebuild: restore the shortened chain(on failure) and identify the source of the failure
            :arg steps: positive integer(optional), number of steps for partial execution
            :raises MonadError: violations of monadic contracts
        """
        result, restored, faulty, last_success = None, None, None, None
        cls = self.__class__
        funcs = _unwind(persist=self)
        first_index, last_index = specs.get_indexes_for_execution(steps, inverted_funcs=funcs)
        for i in range(first_index, last_index, -1):
            result_new = _execute(funcs[i], result)  # since the first func has no params, we can safely pass None
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
                        restored, faulty = cls(funcs[i], past=prime), specs.get_origin(funcs[i])
                        last_success = result
                    else:
                        restored = cls(funcs[i], past=restored)
                else:
                    restored, faulty, last_success = None, None, result_new
            result = result_new

        return Report(result, chain_from_failure=restored, faulty=faulty, last_success=last_success)


def of(value: _Ok) -> ResilientSync[_Ok, Never]:
    """
        Lazy monad for resilient SYNC ONLY effects.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientSync(lambda: value)


def unit(fn: Callable[[], Union[_Ok, _Bad]]) -> ResilientSync[_Ok, _Bad]:
    """
       Lazy monad for resilient SYNC ONLY effects.
       Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
       Automatically catches errors and wraps them in an 'Uncaught' object.
       Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientSync(fn)


def insist(
        resilient: ResilientSync[_Ok, _Bad],
        attempts: int = 1,
        pause_between: Union[int, float] = 0
) -> Report[_Ok, Optional[ResilientSync]]:
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
