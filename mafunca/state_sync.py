from typing import TypeVar, Generic, overload, Union, Optional, List, Tuple
from abc import ABC, abstractmethod
from collections.abc import Callable
from time import sleep

from mafunca.triple import TUtils
from mafunca.common.resilient_support import Uncaught, ReportState, get_indexes_for_execution
from mafunca.common.exceptions import MonadError
import mafunca.common._panics as panics


__all__ = ['of', 'unit', 'StateSync', 'insist']


Exc = TypeVar('Exc', bound=Exception)

R = TypeVar('R')
NewR = TypeVar('NewR')
S = TypeVar('S')

L = TypeVar('L')


_ORIGIN_LINK = "__mafunca_resilient_state_origin__"


def _continuer(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable:
    """
        Special sync closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    def _continuer_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return fn(arg)

    setattr(_continuer_inner, _ORIGIN_LINK, fn)
    return _continuer_inner


def _catcher(fn: Callable) -> Callable:
    """Special sync closure for catching errors"""
    def _catcher_inner(arg):
        if isinstance(arg, Uncaught):
            return fn(arg.error)
        return arg

    setattr(_catcher_inner, _ORIGIN_LINK, fn)
    return _catcher_inner


def _ensurer(fn: Callable[[R], None]) -> Callable:
    """A sync closure simulating finally"""
    def _ensurer_inner(arg):
        fn(arg)
        return arg

    setattr(_ensurer_inner, _ORIGIN_LINK, fn)
    return _ensurer_inner


def _extract_from_closure(closure: Callable) -> Callable:
    """Extract origin function from closures like '_continuer' and etc"""
    origin = getattr(closure, _ORIGIN_LINK, None)
    if origin is None:
        return closure
    return origin


class StateSync(ABC, Generic[R, S]):
    __slots__ = ('_action',)

    def __init__(self, action: Callable[[S], Tuple[R, S]]):
        panics.on_coroutine(action, monad_name=self.__class__.__name__, method='__init__')
        self._action = action

    @overload
    def chain(self, fn: Callable[[R], 'StateSync[NewR, S]']) -> 'StateSync[NewR, S]': pass
    @overload
    def chain(self, fn: Callable[[R], NewR]) -> 'StateSync[NewR, S]': pass

    def chain(self, fn):
        """
            Combines the logic of both 'map' and 'bind' in regular monads.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='chain')
        return _StateSyncCont(_continuer(fn, bad_evaluator=TUtils.is_bad), past=self)

    @overload
    def catch(self, fn: Callable[[Exc], 'StateSync[NewR, S]']) -> 'StateSync[NewR, S]': pass
    @overload
    def catch(self, fn: Callable[[Exc], NewR]) -> 'StateSync[NewR, S]': pass

    def catch(self, fn):
        """
            Handles errors(Exception heirs) that occurred earlier in the chain.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='catch')
        return _StateSyncCont(_catcher(fn), past=self)

    def ensure(self, fn: Callable[[R], None]) -> 'StateSync[R, S]':
        """
            Guaranteed to execute the function-parameter, similar to try finally.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='ensure')
        return _StateSyncCont(_ensurer(fn), past=self)

    @abstractmethod
    def run(
        self,
        state: S,
        rebuild: bool = False,
        cloner: Optional[Callable[[S], S]] = None,
        steps: Optional[int] = None
    ) -> ReportState[R, S, Optional['StateSync']]:
        pass


class _StateSyncPrime(StateSync[R, S]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    def __init__(self, action: Callable[[S], Tuple[R, S]]):
        super().__init__(action)

    @property
    def action(self) -> Callable[[S], Tuple[R, S]]:
        return self._action

    def run(
        self,
        state: S,
        rebuild: bool = False,
        cloner: Optional[Callable[[S], S]] = None,
        steps: Optional[int] = None,
    ) -> ReportState[R, S, Optional['StateSync']]:
        """
            Starts the chain
            :arg state: the initial state passed through the chain
            :arg rebuild: restore the shortened chain(on failure) and identify the source of the failure
            :arg cloner: a function(optional) that copies the state before each step is executed
            :arg steps: positive integer(optional), number of steps for partial execution. Ignored here
            :raises MonadError: violations of monadic contracts
        """
        panics.on_bad_steps_parameter(steps, monad_name='StateSync', method='chain starter method')
        clean_state = cloner(state) if callable(cloner) else None
        try:
            result, changed_state = self._action(state)
        except Exception as exc:
            result, changed_state = Uncaught(exc), state
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            return ReportState(
                result=result,
                state=changed_state,
                chain_from_failure=_StateSyncPrime(self._action),
                faulty=self._action,
                last_success_result=None,
                last_clean_state=clean_state
            )
        return ReportState(
            result=result,
            state=changed_state,
            chain_from_failure=None,
            faulty=None,
            last_success_result=None,
            last_clean_state=clean_state
        )


def _unwind(persist: '_StateSyncCont') -> Tuple['_StateSyncPrime', List[Callable]]:
    """Unwinding the chain to the first effect"""
    current, actions = persist, []
    while isinstance(current, _StateSyncCont):
        actions.append(current.action)
        current = current.past
    if isinstance(current, _StateSyncPrime):
        return current, actions
    raise MonadError(
        monad='StateSync',
        method='chain starter method',
        message="Violation of the usage contract - the first element in the chain must be a 'StateSyncPrime' entity"
    )


def _execute(value: R, fn: Callable[[R], NewR]) -> Union[NewR, Uncaught[Exc]]:
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
        :raises MonadError: panics on coroutine function
    """
    panics.on_coroutine(fn, monad_name='StateSync', method='run')
    try:
        return fn(value)
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _make_effect(val: R) -> Callable[[S], Tuple[R, S]]:
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda state: (val, state)


class _StateSyncCont(StateSync[R, S]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    __slots__ = ('_past',)

    def __init__(self, action: Callable[[S], Tuple[R, S]], past: StateSync):
        super().__init__(action)
        self._past = past

    @property
    def action(self) -> Callable[[S], Tuple[R, S]]:
        return self._action

    @property
    def past(self) -> StateSync:
        return self._past

    def run(
        self,
        state: S,
        rebuild: bool = False,
        cloner: Optional[Callable[[S], S]] = None,
        steps: Optional[int] = None,
    ) -> ReportState[R, S, Optional['StateSync']]:
        """
            Starts the chain
            :arg state: the initial state passed through the chain
            :arg rebuild: restore the shortened chain(on failure) and identify the source of the failure
            :arg cloner: a function(optional) that copies the state before each step is executed
            :arg steps: positive integer(optional), number of steps for partial execution. Ignored here
            :raises MonadError: violations of monadic contracts
        """
        panics.on_bad_steps_parameter(steps, monad_name='StateSync', method='chain starter method')
        prime, cons = _unwind(persist=self)
        report_prime = prime.run(state, rebuild=rebuild, cloner=cloner)
        result, changed_state = report_prime.result, report_prime.state
        restored, faulty = report_prime.chain_from_failure, report_prime.faulty
        ls_result, lc_state = report_prime.last_success_result, report_prime.last_clean_state

        first_cont_index, last_cont_index = get_indexes_for_execution(steps, inverted_cons=cons)
        for i in range(first_cont_index, last_cont_index, -1):
            result_new = _execute(result, cons[i])
            restored_new, faulty_new = None, None
            ls_result_new, lc_state_new = None, None
            if isinstance(result_new, StateSync):
                rpt = result_new.run(changed_state, rebuild=rebuild, cloner=cloner)
                result_new, changed_state = rpt.result, rpt.state
                restored_new, faulty_new = rpt.chain_from_failure, rpt.faulty
                ls_result_new, lc_state_new = rpt.last_success_result, rpt.last_clean_state

            if rebuild:
                if restored_new:
                    # if we're in this branch, it's the first failure!
                    restored, faulty = restored_new, faulty_new
                    ls_result, lc_state = ls_result_new, lc_state_new
                elif isinstance(result_new, Uncaught) or TUtils.is_bad(result_new):
                    if restored is None:
                        prime = _StateSyncPrime(_make_effect(result))
                        restored, faulty = _StateSyncCont(cons[i], past=prime), _extract_from_closure(cons[i])
                        ls_result = result
                    else:
                        restored = _StateSyncCont(cons[i], past=restored)
                else:
                    restored, faulty = None, None
                    ls_result = result_new
                    if lc_state_new is not None:
                        lc_state = lc_state_new
            result = result_new

        return ReportState(
            result=result,
            state=changed_state,
            chain_from_failure=restored,
            faulty=faulty,
            last_success_result=ls_result,
            last_clean_state=lc_state
        )


def of(value: R) -> StateSync[R, S]:
    """
        Lazy monad for resilient SYNC ONLY statefull actions.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return _StateSyncPrime(lambda state: (value, state))


def unit(fn: Callable[[S], [R, S]]) -> StateSync[R, S]:
    """
       Lazy monad for resilient SYNC ONLY statefull actions.
       Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
       Automatically catches errors and wraps them in an 'Uncaught' object.
       Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return _StateSyncPrime(fn)


def insist(
        state: S,
        resilient: StateSync[R, S],
        cloner: Optional[Callable[[S], S]] = None,
        attempts: int = 1,
        pause_between: Union[int, float] = 0
) -> ReportState[R, S, Optional['StateSync']]:
    """Makes 'attempts' to execute a 'resilient' chain with 'pause_between' intervals between them"""
    chain = resilient
    report = ReportState(None, None, None, None, None, None)

    for _ in range(attempts):
        report = chain.run(state, rebuild=True, cloner=cloner)
        if not report.is_ok:
            chain = report.chain_from_failure
            sleep(pause_between)
            continue
        return report

    return report
