from typing import TypeVar, Generic, overload, Union, Optional, List, Tuple
from collections.abc import Callable
from time import sleep

from mafunca.triple import Left, Nothing, TUtils
from mafunca.common.resilient_support import Uncaught, Report
from mafunca.common.exceptions import MonadError
import mafunca.common.panics as panics


__all__ = ['of', 'unit', 'ResilientSyncPrime', 'ResilientSyncCont', 'insist']


Exc = TypeVar('Exc', bound=Exception)
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
L = TypeVar('L')


def _continuer(fn: Callable, bad_evaluator: Callable[..., bool]) -> Callable:
    """
        Special sync closure for continuation through the standard chain method.
        With short circuits on 'Uncaught' and custom 'bad' entities.
    """
    def _continuer_inner(arg):
        if isinstance(arg, Uncaught) or bad_evaluator(arg):
            return arg
        return fn(arg)

    return _continuer_inner


def _catcher(fn: Callable) -> Callable:
    """Special sync closure for catching errors"""
    def _catcher_inner(arg):
        if isinstance(arg, Uncaught):
            return fn(arg.error)
        return arg

    return _catcher_inner


def _ensurer(fn: Callable) -> Callable:
    """A sync closure simulating finally"""
    def _ensurer_inner(arg):
        fn()
        return arg
    return _ensurer_inner


def _extract_from_closure(closure: Callable) -> Callable:
    """Extract origin function from closures like '_continuer' and etc"""
    cells = getattr(closure, "__closure__", ())
    if cells is None:
        return closure
    if len(cells) == 2:
        return cells[1].cell_contents
    elif len(cells) == 1:
        return cells[0].cell_contents
    else:
        return closure


class _ResilientSync(Generic[A]):
    __slots__ = ('_effect',)

    def __init__(self, effect: Callable[..., A]):
        panics.on_coroutine(effect, monad_name=self.__class__.__name__, method='__init__')
        self._effect = effect

    @overload
    def chain(self: '_ResilientSync[Uncaught[Exc]]', fn: Callable[[B], C]) -> 'ResilientSyncCont[Uncaught[Exc]]': pass
    @overload
    def chain(self: '_ResilientSync[Left[L]]', fn: Callable[[B], C]) -> 'ResilientSyncCont[Left[L]]': pass
    @overload
    def chain(self: '_ResilientSync[Nothing]', fn: Callable[[B], C]) -> 'ResilientSyncCont[Nothing]': pass
    @overload
    def chain(self, fn: Callable[[A], '_ResilientSync[B]']) -> 'ResilientSyncCont[B]': pass
    @overload
    def chain(self, fn: Callable[[A], B]) -> 'ResilientSyncCont[B]': pass

    def chain(self, fn):
        """
            Combines the logic of both 'map' and 'bind' in regular monads.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='chain')
        return ResilientSyncCont(_continuer(fn, bad_evaluator=TUtils.is_bad), past=self)

    @overload
    def catch(self, fn: Callable[[Exc], '_ResilientSync[B]']) -> 'ResilientSyncCont[Union[A, B]]': pass
    @overload
    def catch(self, fn: Callable[[Exc], B]) -> 'ResilientSyncCont[Union[A, B]]': pass

    def catch(self, fn):
        """
            Handles errors(Exception heirs) that occurred earlier in the chain.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='catch')
        return ResilientSyncCont(_catcher(fn), past=self)

    def ensure(self, fn: Callable[[], None]) -> 'ResilientSyncCont[A]':
        """
            Guaranteed to execute the function-parameter, similar to try finally.
            :raises MonadError: panics on coroutine function
        """
        panics.on_coroutine(fn, monad_name=self.__class__.__name__, method='ensure')
        return ResilientSyncCont(_ensurer(fn), past=self)


def _execute(value: A, fn: Callable[[A], B]) -> Union[B, Uncaught[Exc]]:
    """
        Execute function from chain with catching errors.
        MonadError is not suppressed.
        :raises MonadError: panics on coroutine function
    """
    panics.on_coroutine(fn, monad_name='ResilientSync', method='run')
    try:
        result = fn(value)
        if isinstance(result, (ResilientSyncPrime, ResilientSyncCont)):
            report = result.run()   # do not restore internal chains
            result = report.result
        return result
    except Exception as exc:
        if isinstance(exc, MonadError):
            raise exc
        return Uncaught(exc)


def _unwind(persist: 'ResilientSyncCont') -> Tuple['ResilientSyncPrime', List[Callable]]:
    """Unwinding the chain to the first effect"""
    current, effects = persist, []
    while isinstance(current, ResilientSyncCont):
        effects.append(current.effect)
        current = current.past
    if isinstance(current, ResilientSyncPrime):
        return current, effects
    raise MonadError(
        monad='ResilientSync',
        method='chain starter method',
        message="Violation of the usage contract - the first element in the chain must be a 'ResilientSyncPrime' entity"
    )


_SyncSub = TypeVar('_SyncSub', bound=_ResilientSync)


class ResilientSyncPrime(_ResilientSync[A]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    def __init__(self, effect: Callable[[], A]):
        super().__init__(effect)

    @property
    def effect(self) -> Callable[[], A]:
        return self._effect

    def run(self, rebuild: bool = False) -> Report[Union[A, Uncaught], Optional['ResilientSyncPrime']]:
        """
            Starts the chain
            :raises MonadError: panics on coroutine function
        """
        result = _execute(None, lambda _: self._effect())   # lambda for uniformity with '_execute' signature
        restored, faulty = None, None
        if rebuild and (isinstance(result, Uncaught) or TUtils.is_bad(result)):
            restored, faulty = ResilientSyncPrime(self._effect), self._effect
        return Report(result, chain_from_failure=restored, faulty=faulty)


def _make_effect(val: A) -> Callable[[], A]:
    """To prevent lambda from updating the reference when it is reassigned  in a loop"""
    return lambda: val


class ResilientSyncCont(_ResilientSync[B]):
    """Use only for typing purposes. To create monads, use the 'of' and 'unit' functions and chained methods"""

    __slots__ = ('_past',)

    def __init__(self, effect: Callable[[A], B], past: _SyncSub):
        super().__init__(effect)
        self._past = past

    @property
    def effect(self) -> Callable[[A], B]:
        return self._effect

    @property
    def past(self) -> _SyncSub:
        return self._past

    def run(self, rebuild: bool = False) -> Report[Union[B, Uncaught], Optional['ResilientSyncCont']]:
        """
            Starts the chain
            :raises MonadError: panics on coroutine function
        """
        persist_prime, cons = _unwind(persist=self)
        report_prime = persist_prime.run(rebuild=rebuild)
        result, restored, faulty = report_prime.result, report_prime.chain_from_failure, report_prime.faulty

        for i in range(len(cons) - 1, -1, -1):
            result_new = _execute(result, cons[i])
            if rebuild and (isinstance(result_new, Uncaught) or TUtils.is_bad(result_new)):
                if restored is None:
                    prime = ResilientSyncPrime(_make_effect(result))
                    restored, faulty = ResilientSyncCont(cons[i], past=prime), _extract_from_closure(cons[i])
                else:
                    restored = ResilientSyncCont(cons[i], past=restored)
            result = result_new

        if isinstance(result, Uncaught) or TUtils.is_bad(result):
            return Report(result, chain_from_failure=restored, faulty=faulty)
        else:
            return Report(result, chain_from_failure=None, faulty=None)


def of(value: A) -> ResilientSyncPrime[A]:
    """
        Lazy monad for resilient SYNC ONLY effects.
        Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
        Automatically catches errors and wraps them in an 'Uncaught' object.
        Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientSyncPrime(lambda: value)


def unit(fn: Callable[[], A]) -> ResilientSyncPrime[A]:
    """
       Lazy monad for resilient SYNC ONLY effects.
       Resilient means, that if there is a failure in the chain, it can return a short chain from the point of failure.
       Automatically catches errors and wraps them in an 'Uncaught' object.
       Works with bad 'Triple' and 'Uncaught' entities using the short-circuit principle.
    """
    return ResilientSyncPrime(fn)


def insist(
        resilient: Union[ResilientSyncPrime[A], ResilientSyncCont[A]],
        attempts: int = 1,
        pause_between: Union[int, float] = 0
) -> Report[Union[A, Uncaught[Exc]], Optional['ResilientSyncCont']]:
    """Makes 'attempts' to execute a 'resilient' chain with 'pause_between' intervals between them"""
    chain, report = resilient, Report(None, None, None)
    for _ in range(attempts):
        report = chain.run(rebuild=True)
        if not report.is_ok:
            chain = report.chain_from_failure
            sleep(pause_between)
    return report
